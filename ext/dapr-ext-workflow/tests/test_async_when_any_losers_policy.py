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
from durabletask import task as durable_task_module


class FakeTask:
    def __init__(self, name: str):
        self.name = name


class FakeCtx:
    def __init__(self):
        import datetime

        self.current_utc_datetime = datetime.datetime(2024, 1, 1)
        self.instance_id = 'iid-any'

    def call_activity(self, activity, *, input=None, retry_policy=None, metadata=None):
        return FakeTask('activity')

    def create_timer(self, fire_at):
        return FakeTask('timer')


async def wf_when_any(ctx: AsyncWorkflowContext):
    # Two awaitables: an activity and a timer
    a = ctx.call_activity(lambda: None)
    b = ctx.sleep(10)
    first = await ctx.when_any([a, b])
    return first


def test_when_any_yields_once_and_returns_first_result(monkeypatch):
    # Patch durabletask.when_any to avoid requiring real durabletask.Task objects
    monkeypatch.setattr(durable_task_module, 'when_any', lambda tasks: FakeTask('when_any'))
    fake = FakeCtx()
    runner = CoroutineOrchestratorRunner(wf_when_any)
    gen = runner.to_generator(AsyncWorkflowContext(fake), None)

    # Prime; expect a single composite yield
    yielded = gen.send(None)
    assert isinstance(yielded, FakeTask)
    # Send the 'first' completion; generator should complete without yielding again
    try:
        gen.send({'task': 'activity'})
        raise AssertionError('generator should have completed')
    except StopIteration as stop:
        assert stop.value == {'task': 'activity'}
