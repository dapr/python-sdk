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
from dapr.ext.workflow.workflow_runtime import WorkflowRuntime


class FakeTask:
    def __init__(self, name: str):
        self.name = name


class FakeOrchestrationContext:
    def __init__(self):
        import datetime

        self.current_utc_datetime = datetime.datetime(2024, 1, 1)
        self.instance_id = 'iid-errors'
        self.is_replaying = False
        self._custom_status = None
        self.workflow_name = 'wf'
        self.parent_instance_id = None
        self.history_event_sequence = 1
        self.trace_parent = None
        self.trace_state = None
        self.orchestration_span_id = None

    def call_activity(self, activity, *, input=None, retry_policy=None, metadata=None, app_id=None):
        return FakeTask('activity')

    def create_timer(self, fire_at):
        return FakeTask('timer')

    def wait_for_external_event(self, name: str):
        return FakeTask(f'event:{name}')

    def set_custom_status(self, custom_status):
        self._custom_status = custom_status


def drive_raise(gen, exc: Exception):
    # Prime
    task = gen.send(None)
    assert isinstance(task, FakeTask)
    # Simulate runtime failure of yielded task
    try:
        gen.throw(exc)
    except StopIteration as stop:
        return stop.value


async def wf_catches_activity_error(ctx: AsyncWorkflowContext):
    try:
        await ctx.call_activity(lambda: (_ for _ in ()).throw(RuntimeError('boom')))
    except RuntimeError as e:
        return f'caught:{e}'
    return 'not-reached'


def test_activity_error_propagates_into_coroutine_and_can_be_caught():
    fake = FakeOrchestrationContext()
    runner = CoroutineOrchestratorRunner(wf_catches_activity_error)
    gen = runner.to_generator(AsyncWorkflowContext(fake), None)
    result = drive_raise(gen, RuntimeError('boom'))
    assert result == 'caught:boom'


async def wf_returns_sync(ctx: AsyncWorkflowContext):
    return 42


def test_sync_return_is_handled_without_runtime_error():
    fake = FakeOrchestrationContext()
    runner = CoroutineOrchestratorRunner(wf_returns_sync)
    gen = runner.to_generator(AsyncWorkflowContext(fake), None)
    # Prime and complete
    try:
        gen.send(None)
    except StopIteration as stop:
        assert stop.value == 42


class _FakeRegistry:
    def __init__(self):
        self.orchestrators = {}
        self.activities = {}

    def add_named_orchestrator(self, name, fn):
        self.orchestrators[name] = fn

    def add_named_activity(self, name, fn):
        self.activities[name] = fn


class _FakeWorker:
    def __init__(self, *args, **kwargs):
        self._registry = _FakeRegistry()

    def start(self):
        pass

    def stop(self):
        pass


def test_generator_and_async_registration_coexist(monkeypatch):
    # Monkeypatch TaskHubGrpcWorker to avoid real gRPC
    import durabletask.worker as worker_mod

    monkeypatch.setattr(worker_mod, 'TaskHubGrpcWorker', _FakeWorker)

    rt = WorkflowRuntime()

    @rt.workflow(name='gen_wf')
    def gen(ctx):
        yield ctx.create_timer(0)
        return 'ok'

    async def async_wf(ctx: AsyncWorkflowContext):
        await ctx.sleep(0)
        return 'ok'

    rt.register_async_workflow(async_wf, name='async_wf')

    # Verify registry got both entries
    reg = rt._WorkflowRuntime__worker._registry
    assert 'gen_wf' in reg.orchestrators
    assert 'async_wf' in reg.orchestrators

    # Drive generator orchestrator wrapper
    gen_fn = reg.orchestrators['gen_wf']
    g = gen_fn(FakeOrchestrationContext())
    t = next(g)
    assert isinstance(t, FakeTask)
    try:
        g.send(None)
    except StopIteration as stop:
        assert stop.value == 'ok'

    # Also verify CancelledError propagates and can be caught
    import asyncio

    async def wf_cancel(ctx: AsyncWorkflowContext):
        try:
            await ctx.call_activity(lambda: None)
        except asyncio.CancelledError:
            return 'cancelled'
        return 'not-reached'

    runner = CoroutineOrchestratorRunner(wf_cancel)
    gen_2 = runner.to_generator(AsyncWorkflowContext(FakeOrchestrationContext()), None)
    # prime
    next(gen_2)
    try:
        gen_2.throw(asyncio.CancelledError())
    except StopIteration as stop:
        assert stop.value == 'cancelled'
