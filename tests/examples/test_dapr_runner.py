import subprocess
import time
from pathlib import Path
from typing import IO

import pytest

from tests.examples import conftest as examples_conftest
from tests.examples.conftest import BACKGROUND_PORTS, FOREGROUND_PORTS, DaprRunner


@pytest.fixture(autouse=True)
def no_real_process_groups(monkeypatch: pytest.MonkeyPatch) -> None:
    """Fake processes have no real process group to signal."""
    monkeypatch.setattr(
        examples_conftest,
        'terminate_process_group',
        lambda proc, *, force=False: None,
    )


@pytest.fixture(autouse=True)
def ports_always_free(monkeypatch: pytest.MonkeyPatch) -> list[list[int]]:
    """Stubs the port-free gate; returns the port lists it was called with."""
    gated: list[list[int]] = []
    monkeypatch.setattr(
        examples_conftest,
        'wait_for_ports_free',
        lambda ports, *, timeout=30.0: gated.append(list(ports)),
    )
    return gated


SIDECAR_READY_OUTPUT = "✅  You're up and running! Both Dapr and your app logs will appear here.\n"


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

    A real background sidecar writes to the file object passed as ``stdout``
    and keeps running (``poll()`` returns ``None``).
    """

    def __init__(self, output: str, returncode: int | None, stdout: IO[str]) -> None:
        stdout.write(output)
        stdout.flush()
        self._returncode = returncode

    def poll(self) -> int | None:
        return self._returncode

    def wait(self, timeout: int | None = None) -> int:
        return self._returncode or 0


def test_run_pins_ports_the_caller_did_not_set(monkeypatch, tmp_path: Path) -> None:
    argv_seen: list[tuple[str, ...]] = []

    def fake_popen(*args, **kwargs) -> FakeProcess:
        argv_seen.append(kwargs['args'])
        return FakeProcess('done\n')

    monkeypatch.setattr(subprocess, 'Popen', fake_popen)

    DaprRunner(tmp_path).run('--app-id=metadata -- python3 app.py', timeout=1)

    argv = argv_seen[0]
    separator = argv.index('--')
    dapr_argv = argv[:separator]
    for flag, port in FOREGROUND_PORTS.as_flags().items():
        flag_position = dapr_argv.index(flag)
        assert dapr_argv[flag_position + 1] == str(port)
    assert list(argv[separator:]) == ['--', 'python3', 'app.py']


def test_run_keeps_port_flags_the_caller_set(monkeypatch, tmp_path: Path) -> None:
    argv_seen: list[tuple[str, ...]] = []

    def fake_popen(*args, **kwargs) -> FakeProcess:
        argv_seen.append(kwargs['args'])
        return FakeProcess('done\n')

    monkeypatch.setattr(subprocess, 'Popen', fake_popen)

    DaprRunner(tmp_path).run(
        '--app-id pub --dapr-grpc-port=3500 --dapr-http-port 3501 -- python3 pub.py',
        timeout=1,
    )

    argv = argv_seen[0]
    assert '--dapr-grpc-port=3500' in argv
    assert argv.count('--dapr-http-port') == 1
    assert str(FOREGROUND_PORTS.grpc) not in argv
    assert str(FOREGROUND_PORTS.http) not in argv
    assert str(FOREGROUND_PORTS.internal_grpc) in argv
    assert str(FOREGROUND_PORTS.metrics) in argv


def test_run_waits_for_every_listener_port_before_launching(monkeypatch, tmp_path: Path) -> None:
    events: list[str] = []
    gated_ports: list[int] = []

    def fake_gate(ports, *, timeout=30.0) -> None:
        events.append('gate')
        gated_ports.extend(ports)

    def fake_popen(*args, **kwargs) -> FakeProcess:
        events.append('launch')
        return FakeProcess('done\n')

    monkeypatch.setattr(examples_conftest, 'wait_for_ports_free', fake_gate)
    monkeypatch.setattr(subprocess, 'Popen', fake_popen)

    DaprRunner(tmp_path).run('--app-id recv --app-port 8088 -- python3 recv.py', timeout=1)

    assert events == ['gate', 'launch']
    assert sorted(gated_ports) == sorted([8088, *FOREGROUND_PORTS])


def test_start_pins_the_background_port_block(monkeypatch, tmp_path: Path) -> None:
    argv_seen: list[tuple[str, ...]] = []

    def fake_popen(*args, **kwargs) -> FakeBackgroundProcess:
        argv_seen.append(kwargs['args'])
        return FakeBackgroundProcess(SIDECAR_READY_OUTPUT, None, kwargs['stdout'])

    monkeypatch.setattr(subprocess, 'Popen', fake_popen)

    DaprRunner(tmp_path).start('--app-id demo-actor -- uvicorn demo:app', wait=0)

    argv = argv_seen[0]
    for flag, port in BACKGROUND_PORTS.as_flags().items():
        flag_position = argv.index(flag)
        assert argv[flag_position + 1] == str(port)


def test_terminate_sweeps_the_group_even_after_a_clean_exit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    group_kills: list[bool] = []
    monkeypatch.setattr(
        examples_conftest,
        'terminate_process_group',
        lambda proc, *, force=False: group_kills.append(force),
    )

    DaprRunner._terminate(FakeProcess('dapr CLI already exited\n', returncode=0))

    assert group_kills == [True]


def test_start_returns_without_sleeping_when_sidecar_is_already_ready(
    monkeypatch, tmp_path: Path
) -> None:
    def fake_popen(*args, **kwargs) -> FakeBackgroundProcess:
        return FakeBackgroundProcess(SIDECAR_READY_OUTPUT, None, kwargs['stdout'])

    monkeypatch.setattr(subprocess, 'Popen', fake_popen)
    sleeps: list[int] = []
    monkeypatch.setattr(time, 'sleep', sleeps.append)

    DaprRunner(tmp_path).start('--app-id demo-actor -- uvicorn demo:app', wait=30)

    assert sleeps == []


def test_start_polls_every_second_until_sidecar_is_ready(monkeypatch, tmp_path: Path) -> None:
    stdout_files: list[IO[str]] = []

    def fake_popen(*args, **kwargs) -> FakeBackgroundProcess:
        stdout_files.append(kwargs['stdout'])
        return FakeBackgroundProcess('sidecar still starting\n', None, kwargs['stdout'])

    monkeypatch.setattr(subprocess, 'Popen', fake_popen)
    sleeps: list[int] = []

    def sleep_then_become_ready(seconds: int) -> None:
        sleeps.append(seconds)
        if len(sleeps) == 2:
            stdout_files[0].write(SIDECAR_READY_OUTPUT)
            stdout_files[0].flush()

    monkeypatch.setattr(time, 'sleep', sleep_then_become_ready)

    DaprRunner(tmp_path).start('--app-id demo-actor -- uvicorn demo:app', wait=30)

    assert sleeps == [1, 1]


def test_start_gives_up_polling_after_wait_seconds(monkeypatch, tmp_path: Path) -> None:
    def fake_popen(*args, **kwargs) -> FakeBackgroundProcess:
        return FakeBackgroundProcess('sidecar never becomes ready\n', None, kwargs['stdout'])

    monkeypatch.setattr(subprocess, 'Popen', fake_popen)

    clock = {'now': 0.0}
    sleeps: list[int] = []

    def fake_sleep(seconds: int) -> None:
        sleeps.append(seconds)
        clock['now'] += seconds

    monkeypatch.setattr(time, 'monotonic', lambda: clock['now'])
    monkeypatch.setattr(time, 'sleep', fake_sleep)

    DaprRunner(tmp_path).start('--app-id demo-actor -- uvicorn demo:app', wait=3)

    assert sleeps == [1, 1, 1]
