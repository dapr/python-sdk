import shlex
import subprocess
import tempfile
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Callable, Generator, Iterator, TypeVar

import httpx
import pytest

from dapr.clients import DaprClient
from dapr.conf import settings

T = TypeVar('T')

INTEGRATION_DIR = Path(__file__).resolve().parent
COMPONENTS_DIR = INTEGRATION_DIR / 'components'
APPS_DIR = INTEGRATION_DIR / 'apps'


class DaprTestEnvironment:
    """Manages Dapr sidecars and returns SDK clients for programmatic testing.

    Unlike tests.examples.DaprRunner (which captures stdout for output-based assertions), this
    class returns real DaprClient instances so tests can make assertions against SDK return values.
    """

    def __init__(self, default_components: Path = COMPONENTS_DIR) -> None:
        self._default_components = default_components
        self._processes: list[subprocess.Popen[str]] = []
        self._log_files: list[Path] = []
        self._clients: list[DaprClient] = []

    def start_sidecar(
        self,
        app_id: str,
        *,
        grpc_port: int = 50001,
        http_port: int = 3500,
        app_port: int | None = None,
        app_cmd: str | None = None,
        components: Path | None = None,
    ) -> DaprClient:
        """Start a Dapr sidecar and return a connected DaprClient.

        Args:
            app_id: Dapr application ID.
            grpc_port: Sidecar gRPC port.
            http_port: Sidecar HTTP port (also used for the SDK health check).
            app_port: Port the app listens on (implies ``--app-protocol grpc``).
            app_cmd: Shell command to start alongside the sidecar.
            components: Path to component YAML directory.  Defaults to
                ``tests/integration/components/``.
        """
        resources = components or self._default_components

        cmd = [
            'dapr',
            'run',
            '--app-id',
            app_id,
            '--resources-path',
            str(resources),
            '--dapr-grpc-port',
            str(grpc_port),
            '--dapr-http-port',
            str(http_port),
        ]
        if app_port is not None:
            cmd.extend(['--app-port', str(app_port), '--app-protocol', 'grpc'])
        if app_cmd is not None:
            cmd.extend(['--', *shlex.split(app_cmd)])

        with tempfile.NamedTemporaryFile(mode='w', suffix=f'-{app_id}.log', delete=False) as log:
            self._log_files.append(Path(log.name))
            proc = subprocess.Popen(
                cmd,
                cwd=INTEGRATION_DIR,
                stdout=log,
                stderr=subprocess.STDOUT,
                text=True,
            )
        self._processes.append(proc)

        # Point the SDK health check at the actual sidecar HTTP port.
        # DaprHealth.wait_for_sidecar() reads settings.DAPR_HTTP_PORT, which
        # is initialized once at import time and won't reflect a non-default
        # http_port unless we update it here. The DaprClient constructor
        # polls /healthz/outbound on this port, so we don't need to sleep first.
        settings.DAPR_HTTP_PORT = http_port

        client = DaprClient(address=f'127.0.0.1:{grpc_port}')
        self._clients.append(client)

        # /healthz/outbound (polled by DaprClient) only checks sidecar-side
        # readiness. When we launched an app alongside the sidecar, also wait
        # for /v1.0/healthz so invoke_method et al. don't race the app's server.
        if app_cmd is not None:
            _wait_for_app_health(http_port)

        return client

    def cleanup(self) -> None:
        for client in self._clients:
            client.close()
        self._clients.clear()
        for proc in self._processes:
            if proc.poll() is None:
                proc.terminate()
                try:
                    proc.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    proc.kill()
                    proc.wait()
        self._processes.clear()
        for log_path in self._log_files:
            log_path.unlink(missing_ok=True)
        self._log_files.clear()


def _wait_until(
    predicate: Callable[[], T | None],
    timeout: float = 10.0,
    interval: float = 0.1,
) -> T:
    """Poll `predicate` until it returns a truthy value.
    Raises `TimeoutError` if it never returns."""
    deadline = time.monotonic() + timeout
    while True:
        result = predicate()
        if result:
            return result
        if time.monotonic() >= deadline:
            raise TimeoutError(f'wait_until timed out after {timeout}s')
        time.sleep(interval)


def _wait_for_app_health(http_port: int, timeout: float = 30.0) -> None:
    """Poll Dapr's app-facing /v1.0/healthz endpoint until it returns 2xx.

    ``/v1.0/healthz`` requires the app behind the sidecar to be reachable,
    unlike ``/v1.0/healthz/outbound`` which only checks sidecar readiness.
    """
    url = f'http://127.0.0.1:{http_port}/v1.0/healthz'

    def _check() -> bool:
        try:
            response = httpx.get(url, timeout=2.0)
        except httpx.HTTPError:
            return False
        return response.is_success

    _wait_until(_check, timeout=timeout, interval=0.2)


@contextmanager
def _isolate_dapr_settings() -> Iterator[None]:
    """Pin SDK HTTP settings to the local test sidecar for the duration.

    ``DaprHealth.get_api_url()`` consults three settings (see
    ``dapr/clients/http/helpers.py``):

    - ``DAPR_HTTP_ENDPOINT``, if set, wins and bypasses host/port entirely.
    - ``DAPR_RUNTIME_HOST`` is the host component of the fallback URL.
    - ``DAPR_HTTP_PORT`` is the port component of the fallback URL.

    Any of these may be populated from the developer's environment (the Dapr
    CLI sets them); without an override the SDK health check could target the
    wrong sidecar. All three are snapshotted and restored so the test's
    mutations don't leak across modules either.
    """
    originals = {
        'DAPR_HTTP_ENDPOINT': settings.DAPR_HTTP_ENDPOINT,
        'DAPR_RUNTIME_HOST': settings.DAPR_RUNTIME_HOST,
        'DAPR_HTTP_PORT': settings.DAPR_HTTP_PORT,
    }
    settings.DAPR_HTTP_ENDPOINT = None
    settings.DAPR_RUNTIME_HOST = '127.0.0.1'
    try:
        yield
    finally:
        for name, value in originals.items():
            setattr(settings, name, value)


@pytest.fixture(scope='module')
def dapr_env() -> Generator[DaprTestEnvironment, Any, None]:
    """Provides a DaprTestEnvironment for programmatic SDK testing.

    Module-scoped so that all tests in a file share a single Dapr sidecar,
    avoiding port conflicts from rapid start/stop cycles and cutting total
    test time significantly.
    """
    with _isolate_dapr_settings():
        env = DaprTestEnvironment()
        try:
            yield env
        finally:
            env.cleanup()


@pytest.fixture
def wait_until() -> Callable[..., Any]:
    """Returns the ``_wait_until(predicate, timeout=10, interval=0.1)`` helper."""
    return _wait_until


@pytest.fixture(scope='module')
def apps_dir() -> Path:
    return APPS_DIR


@pytest.fixture(scope='module')
def components_dir() -> Path:
    return COMPONENTS_DIR
