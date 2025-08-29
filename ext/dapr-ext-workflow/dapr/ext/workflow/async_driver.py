# -*- coding: utf-8 -*-

"""
Copyright 2025 The Dapr Authors
Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at
    http://www.apache.org/licenses/LICENSE-2.0
Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the specific language governing permissions and
limitations under the License.
"""

from __future__ import annotations

from typing import Any, Awaitable, Callable, Generator, Optional

from durabletask import task

from .sandbox import sandbox_scope

"""
Coroutine-to-generator driver for async workflows.

This module exposes a small driver that executes an async orchestrator
by turning each awaited workflow awaitable into a yielded Durable Task
that the Durable Task runtime can schedule deterministically.
"""


class DaprOperation:
    """Small descriptor that wraps an underlying Durable Task.

    Awaitables used inside async orchestrators yield a DaprOperation from
    their __await__ implementation. The driver intercepts it and yields
    the contained Durable Task to the runtime, then forwards the result
    back into the coroutine.
    """

    def __init__(self, dapr_task: task.Task):
        self.dapr_task = dapr_task


class CoroutineOrchestratorRunner:
    """Wraps an async orchestrator into a generator-compatible runner."""

    def __init__(
        self, async_orchestrator: Callable[..., Awaitable[Any]], *, sandbox_mode: str = 'off'
    ):
        self._async_orchestrator = async_orchestrator
        self._sandbox_mode = sandbox_mode

    def to_generator(
        self, async_ctx: Any, input_data: Optional[Any]
    ) -> Generator[task.Task, Any, Any]:
        """Produce a generator that the Durable Task runtime can drive.

        The generator yields Durable Task tasks and receives their results.
        """
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
            if self._sandbox_mode == 'off':
                awaited = coro.send(None)
            else:
                with sandbox_scope(async_ctx, self._sandbox_mode):
                    awaited = coro.send(None)
        except StopIteration as stop:
            # Completed synchronously
            return stop.value  # type: ignore[misc]

        # Drive the coroutine by yielding the underlying Durable Task(s)
        result: Any = None
        while True:
            try:
                if not isinstance(awaited, DaprOperation):
                    raise TypeError(
                        f'Async workflow yielded unsupported object {type(awaited)!r}; expected DaprOperation'
                    )
                dapr_task = awaited.dapr_task
                # Yield the task to the Durable Task runtime and wait to be resumed with its result
                result = yield dapr_task
                # Send the result back into the async coroutine
                if self._sandbox_mode == 'off':
                    awaited = coro.send(result)
                else:
                    with sandbox_scope(async_ctx, self._sandbox_mode):
                        awaited = coro.send(result)
            except StopIteration as stop:
                return stop.value
            except Exception as exc:  # Propagate failures into the coroutine
                try:
                    if self._sandbox_mode == 'off':
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
                        if self._sandbox_mode == 'off':
                            awaited = coro.throw(base_exc)
                        else:
                            with sandbox_scope(async_ctx, self._sandbox_mode):
                                awaited = coro.throw(base_exc)
                    except StopIteration as stop:
                        return stop.value
                    continue
                raise
