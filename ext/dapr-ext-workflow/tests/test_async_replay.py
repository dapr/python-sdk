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

from datetime import datetime, timedelta

from dapr.ext.workflow.aio import AsyncWorkflowContext, CoroutineOrchestratorRunner


class FakeTask:
    def __init__(self, name: str):
        self.name = name


class FakeCtx:
    def __init__(self, instance_id: str = 'iid-replay', now: datetime | None = None):
        self.current_utc_datetime = now or datetime(2024, 1, 1)
        self.instance_id = instance_id

    def call_activity(self, activity, *, input=None, retry_policy=None, metadata=None):
        return FakeTask(f'activity:{getattr(activity, "__name__", str(activity))}:{input}')

    def create_timer(self, fire_at):
        return FakeTask(f'timer:{fire_at}')

    def wait_for_external_event(self, name: str):
        return FakeTask(f'event:{name}')


def drive_with_history(gen, results):
    """Drive the generator with a pre-baked sequence of results, simulating replay history."""
    try:
        next(gen)
        idx = 0
        while True:
            gen.send(results[idx])
            idx += 1
    except StopIteration as stop:
        return stop.value


async def wf_mixed(ctx: AsyncWorkflowContext):
    # activity
    r1 = await ctx.call_activity(lambda: None, input={'x': 1})
    # timer
    await ctx.sleep(timedelta(seconds=5))
    # event
    e = await ctx.wait_for_external_event('go')
    # deterministic utils
    t = ctx.now()
    u = str(ctx.uuid4())
    return {'a': r1, 'e': e, 't': t.isoformat(), 'u': u}


def test_replay_same_history_same_outputs():
    fake = FakeCtx()
    runner = CoroutineOrchestratorRunner(wf_mixed)
    # Pre-bake results sequence corresponding to activity -> timer -> event
    history = [
        {'task': "activity:lambda:{'x': 1}"},
        None,
        {'event': 42},
    ]
    out1 = drive_with_history(runner.to_generator(AsyncWorkflowContext(fake), None), history)
    out2 = drive_with_history(runner.to_generator(AsyncWorkflowContext(fake), None), history)
    assert out1 == out2
