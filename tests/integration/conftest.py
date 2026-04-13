import signal
import subprocess
import tempfile
import threading
import time
from pathlib import Path
from typing import IO, Any, Generator

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
EXAMPLES_DIR = REPO_ROOT / 'examples'


class DaprRunner:
    """Helper to run `dapr run` commands and capture output."""

    def __init__(self, cwd: Path) -> None:
        self._cwd = cwd
        self._bg_process: subprocess.Popen[str] | None = None
        self._bg_output_file: IO[str] | None = None

    def _spawn(self, args: str) -> subprocess.Popen[str]:
        return subprocess.Popen(
            f'dapr run {args}',
            shell=True,
            cwd=self._cwd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )

    @staticmethod
    def _terminate(proc: subprocess.Popen[str]) -> None:
        if proc.poll() is not None:
            return
        proc.send_signal(signal.SIGTERM)
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait()

    def run(self, args: str, *, timeout: int = 30, until: list[str] | None = None) -> str:
        """Run a foreground command, block until it finishes, and return output.

        Use this for short-lived processes (e.g. a publisher that exits on its
        own). For long-lived background services, use ``start()``/``stop()``.

        Args:
            args: Arguments passed to ``dapr run``.
            timeout: Maximum seconds to wait before killing the process.
            until: If provided, the process is terminated as soon as every
                string in this list has appeared in the accumulated output.
        """
        proc = self._spawn(args)
        lines: list[str] = []
        remaining = set(until) if until else set()
        assert proc.stdout is not None

        # Kill the process if it exceeds the timeout.  A background timer is
        # needed because `for line in proc.stdout` blocks indefinitely when
        # the child never exits.
        timer = threading.Timer(interval=timeout, function=proc.kill)
        timer.start()

        try:
            for line in proc.stdout:
                print(line, end='', flush=True)
                lines.append(line)
                if remaining:
                    output_so_far = ''.join(lines)
                    remaining = {exp for exp in remaining if exp not in output_so_far}
                    if not remaining:
                        break
        finally:
            timer.cancel()
            self._terminate(proc)

        return ''.join(lines)

    def start(self, args: str, *, wait: int = 5) -> subprocess.Popen[str]:
        """Start a long-lived background service and return the process handle.

        Use this for servers/subscribers that must stay alive while a second
        process runs via ``run()``. Call ``stop()`` to terminate and collect
        output. Stdout is written to a temp file to avoid pipe-buffer deadlocks.
        """
        output_file = tempfile.NamedTemporaryFile(mode='w+', suffix='.log', delete=False)
        proc = subprocess.Popen(
            f'dapr run {args}',
            shell=True,
            cwd=self._cwd,
            stdout=output_file,
            stderr=subprocess.STDOUT,
            text=True,
        )
        self._bg_process = proc
        self._bg_output_file = output_file
        time.sleep(wait)
        return proc

    def stop(self, proc: subprocess.Popen[str]) -> str:
        """Stop a background process and return its captured output."""
        self._terminate(proc)
        self._bg_process = None
        return self._read_and_close_output()

    def cleanup(self) -> None:
        """Stop the background process if still running."""
        if self._bg_process is not None:
            self._terminate(self._bg_process)
            self._bg_process = None
            self._read_and_close_output()

    def _read_and_close_output(self) -> str:
        if self._bg_output_file is None:
            return ''
        output_path = Path(self._bg_output_file.name)
        self._bg_output_file.close()
        self._bg_output_file = None
        output = output_path.read_text()
        output_path.unlink(missing_ok=True)
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
    runner.cleanup()
