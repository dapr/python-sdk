"""
Copyright 2025 The Dapr Authors
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

from __future__ import annotations

from typing import Any, Awaitable, Callable, Generator, Optional

from durabletask import task
from durabletask.aio.sandbox import SandboxMode, sandbox_scope


class CoroutineOrchestratorRunner:
    """Wraps an async orchestrator into a generator-compatible runner."""

    def __init__(
        self,
        async_orchestrator: Callable[..., Awaitable[Any]],
        *,
        sandbox_mode: SandboxMode = SandboxMode.OFF,
    ):
        self._async_orchestrator = async_orchestrator
        self._sandbox_mode = sandbox_mode

    def to_generator(
        self, async_ctx: Any, input_data: Optional[Any]
    ) -> Generator[task.Task, Any, Any]:
        # Instantiate the coroutine with or without input depending on signature/usage
        try:
            if input_data is None:
                coro = self._async_orchestrator(async_ctx)
            else:
                coro = self._async_orchestrator(async_ctx, input_data)
        except TypeError:
            # Fallback for orchestrators that only accept a single ctx arg
            coro = self._async_orchestrator(async_ctx)

        # Prime the coroutine
        try:
            if self._sandbox_mode == SandboxMode.OFF:
                awaited = coro.send(None)
            else:
                with sandbox_scope(async_ctx, self._sandbox_mode):
                    awaited = coro.send(None)
        except StopIteration as stop:
            return stop.value  # type: ignore[misc]

        # Drive the coroutine by yielding the underlying Durable Task(s)
        while True:
            try:
                result = yield awaited
                if self._sandbox_mode == SandboxMode.OFF:
                    awaited = coro.send(result)
                else:
                    with sandbox_scope(async_ctx, self._sandbox_mode):
                        awaited = coro.send(result)
            except StopIteration as stop:
                return stop.value
            except Exception as exc:
                try:
                    if self._sandbox_mode == SandboxMode.OFF:
                        awaited = coro.throw(exc)
                    else:
                        with sandbox_scope(async_ctx, self._sandbox_mode):
                            awaited = coro.throw(exc)
                except StopIteration as stop:
                    return stop.value
            except BaseException as base_exc:
                # Handle cancellation that may not derive from Exception in some environments
                try:
                    import asyncio as _asyncio  # local import to avoid hard dep at module import time

                    is_cancel = isinstance(base_exc, _asyncio.CancelledError)
                except Exception:
                    is_cancel = False
                if is_cancel:
                    try:
                        if self._sandbox_mode == SandboxMode.OFF:
                            awaited = coro.throw(base_exc)
                        else:
                            with sandbox_scope(async_ctx, self._sandbox_mode):
                                awaited = coro.throw(base_exc)
                    except StopIteration as stop:
                        return stop.value
                    continue
                raise
