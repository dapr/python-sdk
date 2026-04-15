import shlex
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Any, Generator

import pytest

from dapr.clients import DaprClient

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
        wait: int = 5,
    ) -> DaprClient:
        """Start a Dapr sidecar and return a connected DaprClient.

        Args:
            app_id: Dapr application ID.
            grpc_port: Sidecar gRPC port (must match DAPR_GRPC_PORT setting).
            http_port: Sidecar HTTP port (must match DAPR_HTTP_PORT setting for
                the SDK health check).
            app_port: Port the app listens on (implies ``--app-protocol grpc``).
            app_cmd: Shell command to start alongside the sidecar.
            components: Path to component YAML directory.  Defaults to
                ``tests/integration/components/``.
            wait: Seconds to sleep after launching (before the SDK health check).
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

        # Give the sidecar a moment to bind its ports before the SDK health
        # check starts hitting the HTTP endpoint.
        time.sleep(wait)

        # DaprClient constructor calls DaprHealth.wait_for_sidecar(), which
        # polls http://localhost:{DAPR_HTTP_PORT}/v1.0/healthz/outbound until
        # the sidecar is ready (up to DAPR_HEALTH_TIMEOUT seconds).
        client = DaprClient(address=f'127.0.0.1:{grpc_port}')
        self._clients.append(client)
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


@pytest.fixture(scope='module')
def dapr_env() -> Generator[DaprTestEnvironment, Any, None]:
    """Provides a DaprTestEnvironment for programmatic SDK testing.

    Module-scoped so that all tests in a file share a single Dapr sidecar,
    avoiding port conflicts from rapid start/stop cycles and cutting total
    test time significantly.
    """
    env = DaprTestEnvironment()
    yield env
    env.cleanup()


@pytest.fixture(scope='module')
def apps_dir() -> Path:
    return APPS_DIR


@pytest.fixture(scope='module')
def components_dir() -> Path:
    return COMPONENTS_DIR
