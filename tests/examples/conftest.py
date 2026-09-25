import shlex
import subprocess
import tempfile
import threading
import time
from pathlib import Path
from typing import IO, Any, Generator

import pytest

from tests.port_utils import SidecarPorts, wait_for_ports_free
from tests.process_utils import get_kwargs_for_process_group, terminate_process_group

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
EXAMPLES_DIR = REPO_ROOT / 'examples'
DAPR_SIDECAR_READY_MARKER = "You're up and running!"

# A DaprRunner has at most one background (start/stop) and one foreground
# (run) sidecar alive at a time, so two fixed port blocks cover every test.
FOREGROUND_PORTS = SidecarPorts(http=13601, grpc=13602, internal_grpc=13603, metrics=13604)
BACKGROUND_PORTS = SidecarPorts(http=13611, grpc=13612, internal_grpc=13613, metrics=13614)

PORT_FLAGS = (
    '--dapr-http-port',
    '--dapr-grpc-port',
    '--dapr-internal-grpc-port',
    '--metrics-port',
    '--app-port',
)


def pytest_configure(config: pytest.Config) -> None:
    config.addinivalue_line('markers', 'example_dir(name): set the example directory for a test')


class DaprRunner:
    """Helper to run `dapr run` commands and capture output."""

    def __init__(self, cwd: Path) -> None:
        self._cwd = cwd
        self._bg_process: subprocess.Popen[str] | None = None
        self._bg_output_file: IO[str] | None = None

    @staticmethod
    def _terminate(proc: subprocess.Popen[str]) -> None:
        """Terminates a ``dapr run`` invocation and everything it spawned.

        The group is force-killed even after a clean CLI exit: daprd shuts
        down gracefully after the CLI and there is no value in waiting for
        it in tests — the port gate in ``_prepare_launch`` protects the next
        sidecar against anything the sweep misses.
        """
        if proc.poll() is None:
            terminate_process_group(proc)
            try:
                proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                pass
        terminate_process_group(proc, force=True)
        proc.wait()

    @staticmethod
    def _with_pinned_ports(args: str, ports: SidecarPorts) -> list[str]:
        """Builds the ``dapr run`` argv, pinning any listener port the caller left unset.

        Random CLI ports are never used: the CLI's picker can hand the same
        port to two listeners of one daprd (see "Port allocation" in
        tests/integration/AGENTS.md).
        """
        tokens = shlex.split(args)
        separator = tokens.index('--') if '--' in tokens else len(tokens)
        dapr_tokens = tokens[:separator]

        def is_set(flag: str) -> bool:
            return any(token == flag or token.startswith(f'{flag}=') for token in dapr_tokens)

        additions = [
            token
            for flag, port in ports.as_flags().items()
            if not is_set(flag)
            for token in (flag, str(port))
        ]
        return [*dapr_tokens, *additions, *tokens[separator:]]

    @staticmethod
    def _listener_ports(tokens: list[str]) -> list[int]:
        """Extracts every port the sidecar and its app will bind from the argv."""
        separator = tokens.index('--') if '--' in tokens else len(tokens)
        dapr_tokens = tokens[:separator]

        ports: list[int] = []
        for index, token in enumerate(dapr_tokens):
            for flag in PORT_FLAGS:
                if token == flag:
                    ports.append(int(dapr_tokens[index + 1]))
                elif token.startswith(f'{flag}='):
                    ports.append(int(token.split('=', 1)[1]))
        return ports

    def _prepare_launch(self, args: str, ports: SidecarPorts) -> list[str]:
        """Pins the sidecar's ports and blocks until all of them are bindable."""
        tokens = self._with_pinned_ports(args, ports)
        wait_for_ports_free(self._listener_ports(tokens))
        return tokens

    def run(
        self,
        args: str,
        *,
        timeout: int = 30,
        until: list[str] | None = None,
    ) -> str:
        """Run a foreground command, block until it finishes, and return output.

        Use this for short-lived processes (e.g. a publisher that exits on its
        own). For long-lived background services, use ``start()``/``stop()``.

        Args:
            args: Arguments passed to ``dapr run``. Listener ports not set
                here are pinned from ``FOREGROUND_PORTS``.
            timeout: Maximum seconds to wait before killing the process.
            until: If provided, the process is terminated as soon as every
                string in this list has appeared in the accumulated output.
        """
        tokens = self._prepare_launch(args, FOREGROUND_PORTS)
        proc = subprocess.Popen(
            args=('dapr', 'run', *tokens),
            cwd=self._cwd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            **get_kwargs_for_process_group(),
        )
        lines: list[str] = []
        assert proc.stdout is not None

        # Kill the process if it exceeds the timeout.  A background timer is
        # needed because `for line in proc.stdout` blocks indefinitely when
        # the child never exits.
        timer = threading.Timer(
            interval=timeout, function=lambda: terminate_process_group(proc, force=True)
        )
        timer.start()

        try:
            for line in proc.stdout:
                print(line, end='', flush=True)
                lines.append(line)
                if until and all(exp in ''.join(lines) for exp in until):
                    break
        finally:
            timer.cancel()
            self._terminate(proc)

        return ''.join(lines)

    def start(self, args: str, *, wait: int = 30) -> None:
        """Start a long-lived background service.

        Use this for servers/subscribers that must stay alive while a second
        process runs via ``run()``. Call ``stop()`` to terminate and collect
        output. Stdout is written to a temp file to avoid pipe-buffer deadlocks.

        Args:
            args: Arguments passed to ``dapr run``. Listener ports not set
                here are pinned from ``BACKGROUND_PORTS``.
            wait: Maximum seconds to poll for sidecar readiness before
                proceeding anyway.
        """
        tokens = self._prepare_launch(args, BACKGROUND_PORTS)
        output_file = tempfile.NamedTemporaryFile(mode='w+', suffix='.log')
        proc = subprocess.Popen(
            args=('dapr', 'run', *tokens),
            cwd=self._cwd,
            stdout=output_file,
            stderr=subprocess.STDOUT,
            text=True,
            **get_kwargs_for_process_group(),
        )
        self._wait_until_ready(proc, output_file, timeout=wait)

        self._bg_process = proc
        self._bg_output_file = output_file

    @staticmethod
    def _wait_until_ready(
        proc: subprocess.Popen[str], output_file: IO[str], *, timeout: int
    ) -> None:
        """Polls the sidecar log every second until `dapr run` reports readiness.

        Returns early when the process exits and gives up after ``timeout``
        seconds, at which point the caller proceeds as if ready.

        The log is re-opened by name for each read: the ``output_file`` handle
        shares its offset with the child process, so seeking it directly would
        corrupt the child's writes.
        """
        log_path = Path(output_file.name)
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if proc.poll() is not None:
                return
            if DAPR_SIDECAR_READY_MARKER in log_path.read_text(errors='replace'):
                return
            time.sleep(1)

    def stop(self) -> str:
        """Stop the background service and return its captured output."""
        if self._bg_process is None:
            return ''
        self._terminate(self._bg_process)
        self._bg_process = None
        return self._read_and_close_output()

    def _read_and_close_output(self) -> str:
        if self._bg_output_file is None:
            return ''
        self._bg_output_file.seek(0)
        output = self._bg_output_file.read()
        self._bg_output_file.close()
        self._bg_output_file = None
        print(output, end='', flush=True)
        return output


@pytest.fixture
def dapr(request: pytest.FixtureRequest) -> Generator[DaprRunner, Any, None]:
    """Provides a DaprRunner scoped to an example directory.

    Use the ``example_dir`` marker to select which example:

        @pytest.mark.example_dir('state_store')
        def test_something(dapr):
            ...

    Defaults to the examples root if no marker is set.
    """
    marker = request.node.get_closest_marker('example_dir')
    cwd = EXAMPLES_DIR / marker.args[0] if marker else EXAMPLES_DIR

    runner = DaprRunner(cwd)
    yield runner
    runner.stop()
