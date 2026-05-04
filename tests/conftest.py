import subprocess
from typing import Callable, Iterator

import pytest

from tests.ollama_utils import DEFAULT_MODEL, model_available, ollama_ready
from tests.process_utils import get_kwargs_for_process_group, terminate_process_group
from tests.wait_utils import wait_until

REDIS_CONTAINER = 'dapr_redis'


@pytest.fixture(scope='session')
def flush_redis() -> None:
    """Flush the ``dapr_redis`` container once per session."""
    subprocess.run(
        args=('docker', 'exec', REDIS_CONTAINER, 'redis-cli', 'FLUSHDB'),
        check=True,
        capture_output=True,
        timeout=10,
    )


@pytest.fixture(scope='session')
def redis_set_config() -> Callable[[str, str, int], None]:
    """Dapr encodes values in the config store as ``value||version``"""

    def _set(key: str, value: str, version: int = 1) -> None:
        subprocess.run(
            args=(
                'docker',
                'exec',
                REDIS_CONTAINER,
                'redis-cli',
                'SET',
                key,
                f'{value}||{version}',
            ),
            check=True,
            capture_output=True,
            timeout=10,
        )

    return _set


@pytest.fixture(scope='session')
def ollama() -> Iterator[None]:
    """Ensure an Ollama server with the default model is running for the session."""
    started: subprocess.Popen[str] | None = None
    try:
        if not ollama_ready():
            try:
                started = subprocess.Popen(
                    ['ollama', 'serve'],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    text=True,
                    **get_kwargs_for_process_group(),
                )
            except FileNotFoundError as exc:
                pytest.fail(f'ollama CLI is not installed: {exc}')
            wait_until(ollama_ready, timeout=30.0, interval=0.5)

        if not model_available(DEFAULT_MODEL):
            subprocess.run(['ollama', 'pull', DEFAULT_MODEL], check=True, capture_output=True)

        yield
    finally:
        if started and started.poll() is None:
            terminate_process_group(started)
            try:
                started.wait(timeout=10)
            except subprocess.TimeoutExpired:
                terminate_process_group(started, force=True)
                started.wait()
