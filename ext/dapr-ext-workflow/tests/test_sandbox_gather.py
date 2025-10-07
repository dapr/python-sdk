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

import asyncio
from datetime import datetime, timedelta

import pytest
from durabletask.aio.sandbox import SandboxMode

from dapr.ext.workflow.aio import AsyncWorkflowContext, CoroutineOrchestratorRunner
from dapr.ext.workflow.aio.sandbox import sandbox_scope

"""
Tests for sandboxed asyncio.gather behavior in async orchestrators.
"""


class _FakeCtx:
    def __init__(self):
        self.current_utc_datetime = datetime(2024, 1, 1)
        self.instance_id = 'test-instance'

    def create_timer(self, fire_at):
        class _T:
            def __init__(self):
                self._parent = None
                self.is_complete = False

        return _T()

    def wait_for_external_event(self, name: str):
        class _T:
            def __init__(self):
                self._parent = None
                self.is_complete = False

        return _T()


def drive(gen, results):
    try:
        gen.send(None)
        i = 0
        while True:
            gen.send(results[i])
            i += 1
    except StopIteration as stop:
        return stop.value


async def _plain(value):
    return value


async def awf_empty(ctx: AsyncWorkflowContext):
    with sandbox_scope(ctx, SandboxMode.BEST_EFFORT):
        out = await asyncio.gather()
    return out


def test_sandbox_gather_empty_returns_list():
    fake = _FakeCtx()
    runner = CoroutineOrchestratorRunner(awf_empty)
    gen = runner.to_generator(AsyncWorkflowContext(fake), None)
    out = drive(gen, results=[None])
    assert out == []


async def awf_when_all(ctx: AsyncWorkflowContext):
    a = ctx.create_timer(timedelta(seconds=0))
    b = ctx.wait_for_external_event('x')
    with sandbox_scope(ctx, SandboxMode.BEST_EFFORT):
        res = await asyncio.gather(a, b)
    return res


def test_sandbox_gather_all_workflow_maps_to_when_all():
    fake = _FakeCtx()
    runner = CoroutineOrchestratorRunner(awf_when_all)
    gen = runner.to_generator(AsyncWorkflowContext(fake), None)
    out = drive(gen, results=[[1, 2]])
    assert out == [1, 2]


async def awf_mixed(ctx: AsyncWorkflowContext):
    a = ctx.create_timer(timedelta(seconds=0))
    with sandbox_scope(ctx, SandboxMode.BEST_EFFORT):
        res = await asyncio.gather(a, _plain('ok'))
    return res


def test_sandbox_gather_mixed_returns_sequential_results():
    fake = _FakeCtx()
    runner = CoroutineOrchestratorRunner(awf_mixed)
    gen = runner.to_generator(AsyncWorkflowContext(fake), None)
    out = drive(gen, results=[123])
    assert out == [123, 'ok']


async def awf_return_exceptions(ctx: AsyncWorkflowContext):
    async def _boom():
        raise RuntimeError('x')

    a = ctx.create_timer(timedelta(seconds=0))
    with sandbox_scope(ctx, SandboxMode.BEST_EFFORT):
        res = await asyncio.gather(a, _boom(), return_exceptions=True)
    return res


def test_sandbox_gather_return_exceptions():
    fake = _FakeCtx()
    runner = CoroutineOrchestratorRunner(awf_return_exceptions)
    gen = runner.to_generator(AsyncWorkflowContext(fake), None)
    out = drive(gen, results=[321])
    assert isinstance(out[1], RuntimeError)


async def awf_multi_await(ctx: AsyncWorkflowContext):
    with sandbox_scope(ctx, SandboxMode.BEST_EFFORT):
        g = asyncio.gather()
        a = await g
        b = await g
    return (a, b)


def test_sandbox_gather_multi_await_safe():
    fake = _FakeCtx()
    runner = CoroutineOrchestratorRunner(awf_multi_await)
    gen = runner.to_generator(AsyncWorkflowContext(fake), None)
    out = drive(gen, results=[None])
    assert out == ([], [])


def test_sandbox_gather_restored_outside():
    import asyncio as aio

    original = aio.gather
    fake = _FakeCtx()
    ctx = AsyncWorkflowContext(fake)
    with sandbox_scope(ctx, SandboxMode.BEST_EFFORT):
        pass
    # After exit, gather should be restored
    assert aio.gather is original


def test_strict_mode_blocks_create_task():
    import asyncio as aio

    fake = _FakeCtx()
    ctx = AsyncWorkflowContext(fake)
    with sandbox_scope(ctx, SandboxMode.STRICT):
        if hasattr(aio, 'create_task'):
            with pytest.raises(RuntimeError):
                # Use a dummy coroutine to trigger the block
                async def _c():
                    return 1

                aio.create_task(_c())
