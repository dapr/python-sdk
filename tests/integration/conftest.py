import signal
import subprocess
import threading
import time
from pathlib import Path
from typing import Any, Generator

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
EXAMPLES_DIR = REPO_ROOT / 'examples'


class DaprRunner:
    """Helper to run `dapr run` commands and capture output."""

    def __init__(self, cwd: Path) -> None:
        self._cwd = cwd
        self._bg: subprocess.Popen[str] | None = None
        self._bg_lines: list[str] = []
        self._bg_reader: threading.Thread | None = None

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
        """Run a `dapr run` command, stream output, and return it.

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
        timer = threading.Timer(timeout, proc.kill)
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
        """Start a `dapr run` command in the background and return the handle.

        A reader thread continuously drains stdout so the pipe buffer never
        fills up (which would block the child process).
        """
        proc = self._spawn(args)
        self._bg = proc
        self._bg_lines = []

        def drain() -> None:
            assert proc.stdout is not None
            for line in proc.stdout:
                print(line, end='', flush=True)
                self._bg_lines.append(line)

        self._bg_reader = threading.Thread(target=drain, daemon=True)
        self._bg_reader.start()
        time.sleep(wait)
        return proc

    def stop(self, proc: subprocess.Popen[str]) -> str:
        """Stop a background process and return its captured output."""
        self._terminate(proc)
        self._bg = None
        if self._bg_reader is not None:
            self._bg_reader.join(timeout=5)
            self._bg_reader = None
        output = ''.join(self._bg_lines)
        self._bg_lines = []
        return output

    def cleanup(self) -> None:
        """Stop the background process if still running (teardown safety net)."""
        if self._bg is not None:
            self._terminate(self._bg)
            self._bg = None
            if self._bg_reader is not None:
                self._bg_reader.join(timeout=5)
                self._bg_reader = None
            self._bg_lines = []


def assert_lines_in_output(output: str, expected_lines: list[str], *, ordered: bool = True) -> None:
    """Assert that each expected line appears as a substring in the output.

    Args:
        output: The combined stdout/stderr string.
        expected_lines: List of strings that must appear in the output.
        ordered: If True, the expected lines must appear in order.
    """
    missing = [line for line in expected_lines if line not in output]
    assert not missing, (
        f'Missing expected lines in output:\n  Missing: {missing}\n  Output:\n{output}'
    )

    if not ordered:
        return

    positions = [output.index(line) for line in expected_lines]
    out_of_order = [
        (expected_lines[i], expected_lines[i + 1])
        for i in range(len(positions) - 1)
        if positions[i] > positions[i + 1]
    ]
    assert not out_of_order, (
        f'Lines appeared out of order:\n  Out of order pairs: {out_of_order}\n  Output:\n{output}'
    )


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
