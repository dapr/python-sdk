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

from dapr.ext.workflow.aio import AsyncWorkflowContext, CoroutineOrchestratorRunner


class FakeTask:
    def __init__(self, name: str):
        self.name = name


class FakeCtx:
    def __init__(self):
        self.current_utc_datetime = __import__('datetime').datetime(2024, 1, 1)
        self.instance_id = 'test-instance'
        self._events: dict[str, list] = {}

    def call_activity(self, activity, *, input=None, retry_policy=None, metadata=None, app_id=None):
        return FakeTask(f'activity:{getattr(activity, "__name__", str(activity))}')

    def call_child_workflow(
        self, workflow, *, input=None, instance_id=None, retry_policy=None, metadata=None, app_id=None
    ):
        return FakeTask(f'sub:{getattr(workflow, "__name__", str(workflow))}')

    def create_timer(self, fire_at):
        return FakeTask('timer')

    def wait_for_external_event(self, name: str):
        return FakeTask(f'event:{name}')


def drive(gen, first_result=None):
    """Drive a generator produced by the async driver, emulating the runtime."""
    try:
        task = gen.send(None)
        assert isinstance(task, FakeTask)
        result = first_result
        while True:
            task = gen.send(result)
            assert isinstance(task, FakeTask)
            # Provide a generic result for every yield
            result = {'task': task.name}
    except StopIteration as stop:
        return stop.value


async def sample_activity(ctx: AsyncWorkflowContext):
    return await ctx.call_activity(lambda: None)


def test_activity_awaitable_roundtrip():
    fake = FakeCtx()
    runner = CoroutineOrchestratorRunner(sample_activity)
    gen = runner.to_generator(AsyncWorkflowContext(fake), None)
    result = drive(gen, first_result={'task': 'activity:lambda'})
    assert result == {'task': 'activity:lambda'}


async def sample_timer(ctx: AsyncWorkflowContext):
    await ctx.create_timer(1.0)
    return 'done'


def test_timer_awaitable_roundtrip():
    fake = FakeCtx()
    runner = CoroutineOrchestratorRunner(sample_timer)
    gen = runner.to_generator(AsyncWorkflowContext(fake), None)
    result = drive(gen, first_result=None)
    assert result == 'done'


async def sample_event(ctx: AsyncWorkflowContext):
    data = await ctx.wait_for_external_event('go')
    return ('event', data)


def test_event_awaitable_roundtrip():
    fake = FakeCtx()
    runner = CoroutineOrchestratorRunner(sample_event)
    gen = runner.to_generator(AsyncWorkflowContext(fake), None)
    result = drive(gen, first_result={'hello': 'world'})
    assert result == ('event', {'hello': 'world'})
