import subprocess
import time
from pathlib import Path
from typing import IO

import pytest

from tests.examples.conftest import DaprRunner


class FakeProcess:
    def __init__(self, output: str, returncode: int = 1) -> None:
        self.stdout = iter(output.splitlines(keepends=True))
        self.returncode = returncode

    def poll(self) -> int:
        return self.returncode

    def wait(self, timeout: int | None = None) -> int:
        return self.returncode


class FakeBackgroundProcess:
    """Stand-in for a ``dapr run`` background process started via ``start()``.

    A real background sidecar writes to the file object passed as ``stdout`` and
    keeps running (``poll()`` returns ``None``); a sidecar that died on a port
    bind has exited (``poll()`` returns a non-``None`` code).
    """

    def __init__(self, output: str, returncode: int | None, stdout: IO[str]) -> None:
        stdout.write(output)
        stdout.flush()
        self._returncode = returncode

    def poll(self) -> int | None:
        return self._returncode

    def wait(self, timeout: int | None = None) -> int:
        return self._returncode or 0


def test_run_retries_transient_dapr_port_bind_failure(
    monkeypatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    outputs = [
        (
            'level=error msg="Failed to listen for gRPC server on TCP address :33223 '
            'with error: listen tcp :33223: bind: address already in use"\n'
            'level=fatal msg="Fatal error from runtime: failed to start internal gRPC '
            'server: could not listen on any endpoint"\n'
        ),
        "{'secretKey': 'secretValue'}\n",
    ]
    popen_calls = []

    def fake_popen(*args, **kwargs) -> FakeProcess:
        popen_calls.append((args, kwargs))
        return FakeProcess(outputs.pop(0))

    monkeypatch.setattr(subprocess, 'Popen', fake_popen)
    sleeps: list[int] = []
    monkeypatch.setattr(time, 'sleep', sleeps.append)

    output = DaprRunner(tmp_path).run('--app-id=secretsapp -- python3 example.py', timeout=1)

    assert output == "{'secretKey': 'secretValue'}\n"
    assert len(popen_calls) == 2
    assert sleeps == [1]
    assert (
        'Dapr sidecar failed to bind a random port; retrying startup after 1s'
        in capsys.readouterr().out
    )


def test_run_does_not_retry_non_port_bind_failure(monkeypatch, tmp_path: Path) -> None:
    popen_calls = []

    def fake_popen(*args, **kwargs) -> FakeProcess:
        popen_calls.append((args, kwargs))
        return FakeProcess('application failed before printing expected output\n')

    monkeypatch.setattr(subprocess, 'Popen', fake_popen)

    output = DaprRunner(tmp_path).run('--app-id=secretsapp -- python3 example.py', timeout=1)

    assert output == 'application failed before printing expected output\n'
    assert len(popen_calls) == 1


PORT_BIND_FAILURE_OUTPUT = (
    'level=error msg="Failed to listen for gRPC server on TCP address :38779 '
    'with error: listen tcp :38779: bind: address already in use"\n'
    'level=fatal msg="Fatal error from runtime: failed to start internal gRPC '
    'server: could not listen on any endpoint"\n'
)


def test_start_retries_transient_dapr_port_bind_failure(
    monkeypatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    attempts = [
        (PORT_BIND_FAILURE_OUTPUT, 1),
        ('INFO:     Application startup complete.\n', None),
    ]
    popen_calls = []

    def fake_popen(*args, **kwargs) -> FakeBackgroundProcess:
        popen_calls.append((args, kwargs))
        output, returncode = attempts.pop(0)
        return FakeBackgroundProcess(output, returncode, kwargs['stdout'])

    monkeypatch.setattr(subprocess, 'Popen', fake_popen)
    sleeps: list[int] = []
    monkeypatch.setattr(time, 'sleep', sleeps.append)

    DaprRunner(tmp_path).start('--app-id demo-actor -- uvicorn demo:app', wait=0)

    assert len(popen_calls) == 2
    assert sleeps == [0, 1, 0]
    assert (
        'Dapr background sidecar failed to bind a random port; retrying startup after 1s'
        in capsys.readouterr().out
    )


def test_start_does_not_retry_non_port_bind_failure(monkeypatch, tmp_path: Path) -> None:
    popen_calls = []

    def fake_popen(*args, **kwargs) -> FakeBackgroundProcess:
        popen_calls.append((args, kwargs))
        return FakeBackgroundProcess('app crashed for an unrelated reason\n', 1, kwargs['stdout'])

    monkeypatch.setattr(subprocess, 'Popen', fake_popen)

    DaprRunner(tmp_path).start('--app-id demo-actor -- uvicorn demo:app', wait=0)

    assert len(popen_calls) == 1
