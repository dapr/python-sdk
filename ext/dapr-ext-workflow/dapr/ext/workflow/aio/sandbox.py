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

import asyncio as _asyncio
import random as _random
import time as _time
import uuid as _uuid
from contextlib import ContextDecorator
from typing import Any

from durabletask.aio.sandbox import SandboxMode
from durabletask.deterministic import deterministic_random, deterministic_uuid4

"""
Scoped sandbox patching for async workflows (best-effort, strict).
"""


def _ctx_instance_id(async_ctx: Any) -> str:
    if hasattr(async_ctx, 'instance_id'):
        return getattr(async_ctx, 'instance_id')
    if hasattr(async_ctx, '_base_ctx') and hasattr(async_ctx._base_ctx, 'instance_id'):
        return async_ctx._base_ctx.instance_id
    return ''


def _ctx_now(async_ctx: Any):
    if hasattr(async_ctx, 'now'):
        try:
            return async_ctx.now()
        except Exception:
            pass
    if hasattr(async_ctx, 'current_utc_datetime'):
        return async_ctx.current_utc_datetime
    if hasattr(async_ctx, '_base_ctx') and hasattr(async_ctx._base_ctx, 'current_utc_datetime'):
        return async_ctx._base_ctx.current_utc_datetime
    import datetime as _dt

    return _dt.datetime.utcfromtimestamp(0)


class _Sandbox(ContextDecorator):
    def __init__(self, async_ctx: Any, mode: str):
        self._async_ctx = async_ctx
        self._mode = mode
        self._saved: dict[str, Any] = {}

    def __enter__(self):
        self._saved['asyncio.sleep'] = _asyncio.sleep
        self._saved['asyncio.gather'] = getattr(_asyncio, 'gather', None)
        self._saved['asyncio.create_task'] = getattr(_asyncio, 'create_task', None)
        self._saved['random.random'] = _random.random
        self._saved['random.randrange'] = _random.randrange
        self._saved['random.randint'] = _random.randint
        self._saved['uuid.uuid4'] = _uuid.uuid4
        self._saved['time.time'] = _time.time
        self._saved['time.time_ns'] = getattr(_time, 'time_ns', None)

        rnd = deterministic_random(_ctx_instance_id(self._async_ctx), _ctx_now(self._async_ctx))

        async def _sleep_patched(delay: float, result: Any = None):  # type: ignore[override]
            try:
                if float(delay) <= 0:
                    return await self._saved['asyncio.sleep'](0)
            except Exception:
                return await self._saved['asyncio.sleep'](delay)  # type: ignore[arg-type]

            await self._async_ctx.sleep(delay)
            return result

        def _random_patched() -> float:
            return rnd.random()

        def _randrange_patched(start, stop=None, step=1):
            return rnd.randrange(start, stop, step) if stop is not None else rnd.randrange(start)

        def _randint_patched(a, b):
            return rnd.randint(a, b)

        def _uuid4_patched():
            return deterministic_uuid4(rnd)

        def _time_patched() -> float:
            return float(_ctx_now(self._async_ctx).timestamp())

        def _time_ns_patched() -> int:
            return int(_ctx_now(self._async_ctx).timestamp() * 1_000_000_000)

        def _create_task_blocked(coro, *args, **kwargs):
            try:
                close = getattr(coro, 'close', None)
                if callable(close):
                    try:
                        close()
                    except Exception:
                        pass
            finally:
                raise RuntimeError(
                    'asyncio.create_task is not allowed inside workflow (strict mode)'
                )

        def _is_workflow_awaitable(obj: Any) -> bool:
            try:
                if hasattr(obj, '_to_dapr_task') or hasattr(obj, '_to_task'):
                    return True
            except Exception:
                pass
            try:
                from durabletask import task as _dt

                if isinstance(obj, _dt.Task):
                    return True
            except Exception:
                pass
            return False

        class _OneShot:
            def __init__(self, factory):
                self._factory = factory
                self._done = False
                self._res: Any = None
                self._exc: BaseException | None = None

            def __await__(self):  # type: ignore[override]
                if self._done:

                    async def _replay():
                        if self._exc is not None:
                            raise self._exc
                        return self._res

                    return _replay().__await__()

                async def _compute():
                    try:
                        out = await self._factory()
                        self._res = out
                        self._done = True
                        return out
                    except BaseException as e:  # noqa: BLE001
                        self._exc = e
                        self._done = True
                        raise

                return _compute().__await__()

        def _patched_gather(*aws: Any, return_exceptions: bool = False):  # type: ignore[override]
            if not aws:

                async def _empty():
                    return []

                return _OneShot(_empty)

            if all(_is_workflow_awaitable(a) for a in aws):

                async def _await_when_all():
                    from dapr.ext.workflow.aio.awaitables import WhenAllAwaitable  # local import

                    combined = WhenAllAwaitable(list(aws))
                    return await combined

                return _OneShot(_await_when_all)

            async def _run_mixed():
                results = []
                for a in aws:
                    try:
                        results.append(await a)
                    except Exception as e:  # noqa: BLE001
                        if return_exceptions:
                            results.append(e)
                        else:
                            raise
                return results

            return _OneShot(_run_mixed)

        _asyncio.sleep = _sleep_patched  # type: ignore[assignment]
        if self._saved['asyncio.gather'] is not None:
            _asyncio.gather = _patched_gather  # type: ignore[assignment]
        _random.random = _random_patched  # type: ignore[assignment]
        _random.randrange = _randrange_patched  # type: ignore[assignment]
        _random.randint = _randint_patched  # type: ignore[assignment]
        _uuid.uuid4 = _uuid4_patched  # type: ignore[assignment]
        _time.time = _time_patched  # type: ignore[assignment]
        if self._saved['time.time_ns'] is not None:
            _time.time_ns = _time_ns_patched  # type: ignore[assignment]
        if self._mode == 'strict' and self._saved['asyncio.create_task'] is not None:
            _asyncio.create_task = _create_task_blocked  # type: ignore[assignment]

        return self

    def __exit__(self, exc_type, exc, tb):
        _asyncio.sleep = self._saved['asyncio.sleep']  # type: ignore[assignment]
        if self._saved['asyncio.gather'] is not None:
            _asyncio.gather = self._saved['asyncio.gather']  # type: ignore[assignment]
        if self._saved['asyncio.create_task'] is not None:
            _asyncio.create_task = self._saved['asyncio.create_task']  # type: ignore[assignment]
        _random.random = self._saved['random.random']  # type: ignore[assignment]
        _random.randrange = self._saved['random.randrange']  # type: ignore[assignment]
        _random.randint = self._saved['random.randint']  # type: ignore[assignment]
        _uuid.uuid4 = self._saved['uuid.uuid4']  # type: ignore[assignment]
        _time.time = self._saved['time.time']  # type: ignore[assignment]
        if self._saved['time.time_ns'] is not None:
            _time.time_ns = self._saved['time.time_ns']  # type: ignore[assignment]
        return False


def sandbox_scope(async_ctx: Any, mode: SandboxMode):
    if mode == SandboxMode.OFF:

        class _Null(ContextDecorator):
            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return False

        return _Null()
    return _Sandbox(async_ctx, 'strict' if mode == SandboxMode.STRICT else 'best_effort')
