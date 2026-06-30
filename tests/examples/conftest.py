import shlex
import subprocess
import tempfile
import threading
import time
from pathlib import Path
from typing import IO, Any, Generator

import pytest

from tests.process_utils import get_kwargs_for_process_group, terminate_process_group

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
EXAMPLES_DIR = REPO_ROOT / 'examples'
DAPR_PORT_BIND_FAILURE_MARKERS = (
    'bind: address already in use',
    'failed to start internal gRPC server: could not listen on any endpoint',
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
        if proc.poll() is not None:
            return

        terminate_process_group(proc)
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            terminate_process_group(proc, force=True)
            proc.wait()

    @staticmethod
    def _is_dapr_port_bind_failure(output: str) -> bool:
        return all(marker in output for marker in DAPR_PORT_BIND_FAILURE_MARKERS)

    def run(
        self,
        args: str,
        *,
        timeout: int = 30,
        until: list[str] | None = None,
        port_bind_retries: int = 3,
    ) -> str:
        """Run a foreground command, block until it finishes, and return output.

        Use this for short-lived processes (e.g. a publisher that exits on its
        own). For long-lived background services, use ``start()``/``stop()``.

        Args:
            args: Arguments passed to ``dapr run``.
            timeout: Maximum seconds to wait before killing the process.
            until: If provided, the process is terminated as soon as every
                string in this list has appeared in the accumulated output.
            port_bind_retries: Retry count for Dapr sidecar startup failures
                caused by a transient random-port collision.
        """
        attempts = max(1, port_bind_retries + 1)
        for attempt in range(attempts):
            output = self._run_once(args, timeout=timeout, until=until)
            if attempt < attempts - 1 and self._is_dapr_port_bind_failure(output):
                print(
                    'Dapr sidecar failed to bind a random port; '
                    f'retrying startup after {2**attempt}s '
                    f'(attempt {attempt + 1}/{attempts})',
                    flush=True,
                )
                time.sleep(2**attempt)
                continue
            return output

    def _run_once(self, args: str, *, timeout: int, until: list[str] | None) -> str:
        proc = subprocess.Popen(
            args=('dapr', 'run', *shlex.split(args)),
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

    def start(self, args: str, *, wait: int = 5, port_bind_retries: int = 3) -> None:
        """Start a long-lived background service.

        Use this for servers/subscribers that must stay alive while a second
        process runs via ``run()``. Call ``stop()`` to terminate and collect
        output. Stdout is written to a temp file to avoid pipe-buffer deadlocks.

        Args:
            args: Arguments passed to ``dapr run``.
            wait: Seconds to wait for the sidecar to come up before returning.
            port_bind_retries: Retry count for Dapr sidecar startup failures
                caused by a transient random-port collision.
        """
        attempts = max(1, port_bind_retries + 1)
        for attempt in range(attempts):
            output_file = tempfile.NamedTemporaryFile(mode='w+', suffix='.log')
            proc = subprocess.Popen(
                args=('dapr', 'run', *shlex.split(args)),
                cwd=self._cwd,
                stdout=output_file,
                stderr=subprocess.STDOUT,
                text=True,
                **get_kwargs_for_process_group(),
            )
            time.sleep(wait)

            can_retry = attempt < attempts - 1
            if can_retry and self._started_with_port_bind_failure(proc, output_file):
                self._terminate(proc)
                output_file.close()
                print(
                    'Dapr background sidecar failed to bind a random port; '
                    f'retrying startup after {2**attempt}s '
                    f'(attempt {attempt + 1}/{attempts})',
                    flush=True,
                )
                time.sleep(2**attempt)
                continue

            self._bg_process = proc
            self._bg_output_file = output_file
            return

    def _started_with_port_bind_failure(
        self, proc: subprocess.Popen[str], output_file: IO[str]
    ) -> bool:
        """Whether a background sidecar already exited from a random-port collision.

        Reads the log only once the process has exited; seeking the temp file
        while daprd is still writing would corrupt its shared append offset.
        """
        if proc.poll() is None:
            return False
        output_file.seek(0)
        return self._is_dapr_port_bind_failure(output_file.read())

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
