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

from datetime import datetime

from dapr.ext.workflow.aio import AsyncWorkflowContext, CoroutineOrchestratorRunner
from durabletask import task as durable_task_module
from durabletask.deterministic import deterministic_random, deterministic_uuid4


class FakeTask:
    def __init__(self, name: str):
        self.name = name


class FakeCtx:
    def __init__(self):
        self.current_utc_datetime = datetime(2024, 1, 1)
        self.instance_id = 'iid-123'

    def call_activity(self, activity, *, input=None, retry_policy=None, metadata=None):
        return FakeTask(f'activity:{getattr(activity, "__name__", str(activity))}')

    def call_child_workflow(
        self, workflow, *, input=None, instance_id=None, retry_policy=None, metadata=None
    ):
        return FakeTask(f'sub:{getattr(workflow, "__name__", str(workflow))}')

    def create_timer(self, fire_at):
        return FakeTask('timer')

    def wait_for_external_event(self, name: str):
        return FakeTask(f'event:{name}')


def drive_first_wins(gen, winner_name):
    # Simulate when_any: first send the winner, then finish
    next(gen)  # prime
    result = gen.send({'task': winner_name})
    # the coroutine should complete; StopIteration will be raised by caller
    return result


async def wf_when_all(ctx: AsyncWorkflowContext):
    a = ctx.call_activity(lambda: None)
    b = ctx.sleep(1.0)
    res = await ctx.when_all([a, b])
    return res


def test_when_all_maps_and_completes(monkeypatch):
    # Patch durabletask.when_all to accept our FakeTask inputs and return a FakeTask
    monkeypatch.setattr(durable_task_module, 'when_all', lambda tasks: FakeTask('when_all'))
    fake = FakeCtx()
    runner = CoroutineOrchestratorRunner(wf_when_all)
    gen = runner.to_generator(AsyncWorkflowContext(fake), None)
    # Drive two yields: when_all yields a task once; we simply return a list result
    try:
        t = gen.send(None)
        assert isinstance(t, FakeTask)
        out = gen.send([{'task': 'activity:lambda'}, {'task': 'timer'}])
    except StopIteration as stop:
        out = stop.value
    assert isinstance(out, list)
    assert len(out) == 2


async def wf_when_any(ctx: AsyncWorkflowContext):
    a = ctx.call_activity(lambda: None)
    b = ctx.sleep(5.0)
    first = await ctx.when_any([a, b])
    # Return the first result only; losers ignored deterministically
    return first


def test_when_any_first_wins_behavior(monkeypatch):
    monkeypatch.setattr(durable_task_module, 'when_any', lambda tasks: FakeTask('when_any'))
    fake = FakeCtx()
    runner = CoroutineOrchestratorRunner(wf_when_any)
    gen = runner.to_generator(AsyncWorkflowContext(fake), None)
    try:
        t = gen.send(None)
        assert isinstance(t, FakeTask)
        out = gen.send({'task': 'activity:lambda'})
    except StopIteration as stop:
        out = stop.value
    assert out == {'task': 'activity:lambda'}


def test_deterministic_random_and_uuid_are_stable():
    iid = 'iid-123'
    now = datetime(2024, 1, 1)
    rnd1 = deterministic_random(iid, now)
    rnd2 = deterministic_random(iid, now)
    seq1 = [rnd1.random() for _ in range(5)]
    seq2 = [rnd2.random() for _ in range(5)]
    assert seq1 == seq2
    u1 = deterministic_uuid4(deterministic_random(iid, now))
    u2 = deterministic_uuid4(deterministic_random(iid, now))
    assert u1 == u2
