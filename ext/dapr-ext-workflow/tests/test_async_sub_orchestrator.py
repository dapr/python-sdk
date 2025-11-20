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

import pytest
from dapr.ext.workflow.aio import AsyncWorkflowContext, CoroutineOrchestratorRunner


class FakeTask:
    def __init__(self, name: str):
        self.name = name


class FakeCtx:
    def __init__(self):
        import datetime

        self.current_utc_datetime = datetime.datetime(2024, 1, 1)
        self.instance_id = 'iid-sub'

    def call_activity(self, activity, *, input=None, retry_policy=None, metadata=None):
        return FakeTask('activity')

    def call_child_workflow(
        self, workflow, *, input=None, instance_id=None, retry_policy=None, metadata=None
    ):
        return FakeTask(f'sub:{getattr(workflow, "__name__", str(workflow))}')

    def create_timer(self, fire_at):
        return FakeTask('timer')

    def wait_for_external_event(self, name: str):
        return FakeTask(f'event:{name}')


def drive_success(gen, results):
    try:
        next(gen)
        idx = 0
        while True:
            gen.send(results[idx])
            idx += 1
    except StopIteration as stop:
        return stop.value


def drive_raise(gen, exc: Exception):
    # Prime
    next(gen)
    # Throw failure into orchestrator
    return pytest.raises(Exception, gen.throw, exc)


async def child(ctx: AsyncWorkflowContext, n: int) -> int:
    return n * 2


async def parent_success(ctx: AsyncWorkflowContext):
    res = await ctx.call_child_workflow(child, input=3)
    return res + 1


def test_sub_orchestrator_success():
    fake = FakeCtx()
    runner = CoroutineOrchestratorRunner(parent_success)
    gen = runner.to_generator(AsyncWorkflowContext(fake), None)
    # First yield is the sub-orchestrator task
    result = drive_success(gen, results=[6])
    assert result == 7


async def parent_failure(ctx: AsyncWorkflowContext):
    # Do not catch; allow failure to propagate
    await ctx.call_child_workflow(child, input=1)
    return 'not-reached'


def test_sub_orchestrator_failure_raises_into_orchestrator():
    fake = FakeCtx()
    runner = CoroutineOrchestratorRunner(parent_failure)
    gen = runner.to_generator(AsyncWorkflowContext(fake), None)
    # Prime and then throw into the coroutine to simulate child failure
    next(gen)
    with pytest.raises(RuntimeError, match='child failed'):
        gen.throw(RuntimeError('child failed'))
