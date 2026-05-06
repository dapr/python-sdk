# -*- coding: utf-8 -*-

"""
Copyright 2026 The Dapr Authors
Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at
    http://www.apache.org/licenses/LICENSE-2.0
Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
"""

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
