import subprocess
import time
from pathlib import Path

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
