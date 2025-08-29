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

import asyncio as _asyncio
import random as _random
import time as _time
import uuid as _uuid
from contextlib import ContextDecorator
from typing import Any

from .deterministic import deterministic_random, deterministic_uuid4

"""
Scoped sandbox patching for async workflows (best-effort, strict).

Patches selected stdlib functions to deterministic, workflow-scoped equivalents:
- asyncio.sleep -> ctx.sleep
- random.random/randrange/randint -> deterministic PRNG
- uuid.uuid4 -> deterministic UUID from PRNG
- time.time/time_ns -> orchestration time

Strict mode additionally blocks asyncio.create_task.
"""


def _ctx_instance_id(async_ctx: Any) -> str:
    if hasattr(async_ctx, 'instance_id'):
        return getattr(async_ctx, 'instance_id')  # AsyncWorkflowContext may not expose this
    if hasattr(async_ctx, '_base_ctx') and hasattr(async_ctx._base_ctx, 'instance_id'):
        return async_ctx._base_ctx.instance_id
    return ''


def _ctx_now(async_ctx: Any):
    # Prefer AsyncWorkflowContext.now()
    if hasattr(async_ctx, 'now'):
        try:
            return async_ctx.now()
        except Exception:
            pass
    # Fallback to base ctx attribute
    if hasattr(async_ctx, 'current_utc_datetime'):
        return async_ctx.current_utc_datetime
    if hasattr(async_ctx, '_base_ctx') and hasattr(async_ctx._base_ctx, 'current_utc_datetime'):
        return async_ctx._base_ctx.current_utc_datetime
    # Last resort: wall clock (not ideal, used only in tests)
    import datetime as _dt

    return _dt.datetime.utcfromtimestamp(0)


class _Sandbox(ContextDecorator):
    def __init__(self, async_ctx: Any, mode: str):
        self._async_ctx = async_ctx
        self._mode = mode
        self._saved: dict[str, Any] = {}

    def __enter__(self):
        # Save originals
        self._saved['asyncio.sleep'] = _asyncio.sleep
        self._saved['asyncio.create_task'] = getattr(_asyncio, 'create_task', None)
        self._saved['random.random'] = _random.random
        self._saved['random.randrange'] = _random.randrange
        self._saved['random.randint'] = _random.randint
        self._saved['uuid.uuid4'] = _uuid.uuid4
        self._saved['time.time'] = _time.time
        self._saved['time.time_ns'] = getattr(_time, 'time_ns', None)

        rnd = deterministic_random(_ctx_instance_id(self._async_ctx), _ctx_now(self._async_ctx))

        async def _sleep_patched(delay: float, result: Any = None):  # type: ignore[override]
            # Many libraries (e.g., anyio/httpcore) use asyncio.sleep(0) as a checkpoint.
            # Forward zero-or-negative delays to the original asyncio.sleep to avoid
            # yielding workflow awaitables outside the orchestrator driver.
            try:
                if float(delay) <= 0:
                    return await self._saved['asyncio.sleep'](0)
            except Exception:
                # If delay cannot be coerced, fall back to original behavior
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

        def _create_task_blocked(coro, *args, **kwargs):  # strict only
            # Close the coroutine to avoid "was never awaited" warnings when create_task is blocked
            try:
                close = getattr(coro, 'close', None)
                if callable(close):
                    try:
                        close()
                    except Exception:
                        # Swallow any error while closing; we are about to raise a policy error
                        pass
            finally:
                raise RuntimeError('asyncio.create_task is not allowed inside workflow (strict mode)')

        # Apply patches
        _asyncio.sleep = _sleep_patched  # type: ignore[assignment]
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
        # Restore originals
        _asyncio.sleep = self._saved['asyncio.sleep']  # type: ignore[assignment]
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


def sandbox_scope(async_ctx: Any, mode: str):
    if mode not in ('off', 'best_effort', 'strict'):
        mode = 'off'
    if mode == 'off':
        # no-op context manager
        class _Null(ContextDecorator):
            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return False

        return _Null()
    return _Sandbox(async_ctx, mode)
