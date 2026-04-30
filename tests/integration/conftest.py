import shlex
import shutil
import subprocess
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Generator, Iterator

import httpx
import pytest

from dapr.clients import DaprClient
from dapr.conf import settings
from tests.crypto_utils import remove_test_keys, write_test_keys
from tests.process_utils import get_kwargs_for_process_group, terminate_process_group
from tests.wait_utils import wait_until

INTEGRATION_DIR = Path(__file__).resolve().parent
RESOURCES_DIR = INTEGRATION_DIR / 'resources'
APPS_DIR = INTEGRATION_DIR / 'apps'

BINDING_DATA_DIR = INTEGRATION_DIR / '.binding-data'
CRYPTO_KEYS_DIR = INTEGRATION_DIR / 'keys'


class DaprTestEnvironment:
    """Manages Dapr sidecars and returns SDK clients for programmatic testing.

    Unlike tests.examples.DaprRunner (which captures stdout for output-based assertions), this
    class returns real DaprClient instances so tests can make assertions against SDK return values.
    """

    def __init__(self, default_resources: Path = RESOURCES_DIR) -> None:
        self.default_resources = default_resources
        self.processes: list[subprocess.Popen[str]] = []
        self.clients: list[DaprClient] = []

    def start_sidecar(
        self,
        app_id: str,
        *,
        grpc_port: int = 50001,
        http_port: int = 3500,
        app_port: int | None = None,
        app_cmd: str | None = None,
        resources: Path | None = None,
    ) -> DaprClient:
        """Start a Dapr sidecar and return a connected DaprClient.

        Args:
            app_id: Dapr application ID.
            grpc_port: Sidecar gRPC port.
            http_port: Sidecar HTTP port (also used for the SDK health check).
            app_port: Port the app listens on (implies ``--app-protocol grpc``).
            app_cmd: Shell command to start alongside the sidecar.
            resources: Path to resources YAML directory.  Defaults to
                ``tests/integration/resources/``.
        """
        resources = resources or self.default_resources

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

        proc = subprocess.Popen(
            cmd,
            cwd=INTEGRATION_DIR,
            text=True,
            **get_kwargs_for_process_group(),
        )
        self.processes.append(proc)

        # Point the SDK health check at the actual sidecar HTTP port.
        # DaprHealth.wait_for_sidecar() reads settings.DAPR_HTTP_PORT, which
        # is initialized once at import time and won't reflect a non-default
        # http_port unless we update it here. The DaprClient constructor
        # polls /healthz/outbound on this port, so we don't need to sleep first.
        settings.DAPR_HTTP_PORT = http_port

        client = DaprClient(address=f'127.0.0.1:{grpc_port}')
        self.clients.append(client)

        # /healthz/outbound (polled by DaprClient) only checks sidecar-side
        # readiness. When we launched an app alongside the sidecar, also wait
        # for /v1.0/healthz so invoke_method et al. don't race the app's server.
        if app_cmd is not None:
            _wait_for_app_health(http_port)

        return client

    def cleanup(self) -> None:
        for client in self.clients:
            client.close()
        self.clients.clear()

        for proc in self.processes:
            if proc.poll() is None:
                terminate_process_group(proc)
                try:
                    proc.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    terminate_process_group(proc, force=True)
                    proc.wait()
        self.processes.clear()


def _wait_for_app_health(http_port: int, timeout: float = 30.0) -> None:
    """Poll Dapr's app-facing /v1.0/healthz endpoint until it returns 2xx.

    ``/v1.0/healthz`` requires the app behind the sidecar to be reachable,
    unlike ``/v1.0/healthz/outbound`` which only checks sidecar readiness.
    """
    url = f'http://127.0.0.1:{http_port}/v1.0/healthz'

    def _check() -> bool:
        try:
            return httpx.get(url, timeout=2.0).is_success
        except httpx.HTTPError:
            return False

    wait_until(_check, timeout=timeout, interval=0.2)


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
    avoiding port conflicts from rapid start/stop cycles.
    """
    with _isolate_dapr_settings():
        env = DaprTestEnvironment()
        try:
            yield env
        finally:
            env.cleanup()


@pytest.fixture(autouse=True)
def fail_if_dead_sidecars(dapr_env: DaprTestEnvironment) -> None:
    """Fail the next test cleanly if a managed sidecar has died.

    Without this, a crashed sidecar produces a cascade of gRPC connection
    timeouts on every subsequent test in the module.
    """
    dead = [proc for proc in dapr_env.processes if proc.poll() is not None]
    if not dead:
        return
    details = ', '.join(f'pid={p.pid} exit={p.returncode}' for p in dead)
    raise RuntimeError(f'Dapr sidecar exited unexpectedly: {details}')


@pytest.fixture(scope='module')
def apps_dir() -> Path:
    return APPS_DIR


@pytest.fixture(scope='module')
def resources_dir() -> Path:
    return RESOURCES_DIR


@pytest.fixture(scope='session', autouse=True)
def _binding_data_dir() -> Generator[None, None, None]:
    """Provide a fresh ``.binding-data/`` for the localbinding component"""
    shutil.rmtree(BINDING_DATA_DIR, ignore_errors=True)
    BINDING_DATA_DIR.mkdir(parents=True, exist_ok=True)
    try:
        yield
    finally:
        shutil.rmtree(BINDING_DATA_DIR, ignore_errors=True)


@pytest.fixture(scope='session', autouse=True)
def crypto_keys() -> Generator[Path, None, None]:
    """Generate temporary RSA + AES keys for ``cryptostore.yaml``.

    Note: autouse is necessary because all sidecars load the entire resources/ folder, regardless
    of which components they actually test.
    """
    write_test_keys(CRYPTO_KEYS_DIR)
    try:
        yield CRYPTO_KEYS_DIR
    finally:
        remove_test_keys(CRYPTO_KEYS_DIR)
