import subprocess
from typing import Callable

import pytest

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
