import asyncio
import time
from typing import Awaitable, Callable, TypeVar

T = TypeVar('T')


def wait_until(
    condition: Callable[[], T | None],
    timeout: float = 10.0,
    interval: float = 0.1,
) -> T:
    """Poll ``condition`` until it returns a truthy value.

    Raises ``TimeoutError`` if the deadline elapses first.
    """
    deadline = time.monotonic() + timeout
    while True:
        result = condition()
        if result:
            return result
        if time.monotonic() >= deadline:
            raise TimeoutError(f'wait_until timed out after {timeout}s')
        time.sleep(interval)


async def wait_until_async(
    condition: Callable[[], Awaitable[T | None]],
    timeout: float = 10.0,
    interval: float = 0.1,
) -> T:
    """Async counterpart to `wait_until`: polls an awaitable condition."""
    deadline = time.monotonic() + timeout
    while True:
        result = await condition()
        if result:
            return result
        if time.monotonic() >= deadline:
            raise TimeoutError(f'wait_until_async timed out after {timeout}s')
        await asyncio.sleep(interval)
