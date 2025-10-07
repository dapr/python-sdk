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
See the License for the specific language governing permissions and
limitations under the License.
"""

import asyncio
import random
import time

import pytest
from durabletask.aio.errors import SandboxViolationError
from durabletask.aio.sandbox import SandboxMode

from dapr.ext.workflow.aio import AsyncWorkflowContext, CoroutineOrchestratorRunner


class FakeTask:
    def __init__(self, name: str):
        self.name = name


class FakeCtx:
    def __init__(self):
        self.current_utc_datetime = __import__('datetime').datetime(2024, 1, 1)
        self.instance_id = 'iid-sandbox'

    def call_activity(self, activity, *, input=None, retry_policy=None, metadata=None):
        return FakeTask('activity')

    def create_timer(self, fire_at):
        return FakeTask('timer')

    def wait_for_external_event(self, name: str):
        return FakeTask(f'event:{name}')


async def wf_sleep(ctx: AsyncWorkflowContext):
    # asyncio.sleep should be patched to workflow timer
    await asyncio.sleep(0.1)
    return 'ok'


def drive(gen, first_result=None):
    try:
        task = gen.send(None)
        assert isinstance(task, FakeTask)
        result = first_result
        while True:
            task = gen.send(result)
            assert isinstance(task, FakeTask)
            result = None
    except StopIteration as stop:
        return stop.value


def test_sandbox_best_effort_patches_sleep():
    fake = FakeCtx()
    runner = CoroutineOrchestratorRunner(wf_sleep, sandbox_mode=SandboxMode.BEST_EFFORT)
    gen = runner.to_generator(AsyncWorkflowContext(fake), None)
    result = drive(gen)
    assert result == 'ok'


def test_sandbox_random_uuid_time_are_deterministic():
    fake = FakeCtx()
    runner = CoroutineOrchestratorRunner(
        lambda ctx: _wf_random_uuid_time(ctx), sandbox_mode=SandboxMode.BEST_EFFORT
    )
    gen1 = runner.to_generator(AsyncWorkflowContext(fake), None)
    out1 = drive(gen1)
    gen2 = runner.to_generator(AsyncWorkflowContext(fake), None)
    out2 = drive(gen2)
    assert out1 == out2


async def _wf_random_uuid_time(ctx: AsyncWorkflowContext):
    r1 = random.random()
    u1 = __import__('uuid').uuid4()
    t1 = time.time(), getattr(time, 'time_ns', lambda: int(time.time() * 1_000_000_000))()
    # no awaits needed; return tuple
    return (r1, str(u1), t1[0], t1[1])


def test_strict_blocks_create_task():
    async def wf(ctx: AsyncWorkflowContext):
        with pytest.raises(SandboxViolationError):
            asyncio.create_task(asyncio.sleep(0))
        return 'ok'

    fake = FakeCtx()
    runner = CoroutineOrchestratorRunner(wf, sandbox_mode=SandboxMode.STRICT)
    gen = runner.to_generator(AsyncWorkflowContext(fake), None)
    result = drive(gen)
    assert result == 'ok'
