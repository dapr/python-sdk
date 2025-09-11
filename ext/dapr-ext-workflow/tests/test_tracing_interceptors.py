# -*- coding: utf-8 -*-

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from dapr.ext.workflow import (
    ClientInterceptor,
    DaprWorkflowClient,
    RuntimeInterceptor,
    WorkflowRuntime,
)


class _FakeRegistry:
    def __init__(self):
        self.orchestrators: dict[str, Any] = {}
        self.activities: dict[str, Any] = {}

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


class _FakeOrchestrationContext:
    def __init__(self, *, is_replaying: bool = False):
        self.instance_id = 'wf-1'
        self.current_utc_datetime = datetime(2025, 1, 1)
        self.is_replaying = is_replaying


def _drive_generator(gen, returned_value):
    # Prime to first yield; then drive
    t = next(gen)
    while True:
        try:
            t = gen.send(returned_value)
        except StopIteration as stop:
            return stop.value


def test_client_injects_tracing_on_schedule(monkeypatch):
    import durabletask.client as client_mod

    # monkeypatch TaskHubGrpcClient to capture inputs
    scheduled: dict[str, Any] = {}

    class _FakeClient:
        def __init__(self, *args, **kwargs):
            pass

        def schedule_new_orchestration(self, name, *, input=None, instance_id=None, start_at=None, reuse_id_policy=None):
            scheduled['name'] = name
            scheduled['input'] = input
            scheduled['instance_id'] = instance_id
            scheduled['start_at'] = start_at
            scheduled['reuse_id_policy'] = reuse_id_policy
            return 'id-1'

    monkeypatch.setattr(client_mod, 'TaskHubGrpcClient', _FakeClient)

    class _TracingClient(ClientInterceptor):
        def schedule_new_workflow(self, input, next):  # type: ignore[override]
            tr = {'trace_id': uuid.uuid4().hex}
            if isinstance(input.args, dict) and 'tracing' not in input.args:
                input = type(input)(
                    workflow_name=input.workflow_name,
                    args={**input.args, 'tracing': tr},
                    instance_id=input.instance_id,
                    start_at=input.start_at,
                    reuse_id_policy=input.reuse_id_policy,
                )
            return next(input)

    client = DaprWorkflowClient(interceptors=[_TracingClient()])

    # We only need a callable with a __name__ for scheduling
    def wf(ctx):
        yield 'noop'

    wf.__name__ = 'inject_test'
    instance_id = client.schedule_new_workflow(wf, input={'a': 1})
    assert instance_id == 'id-1'
    assert scheduled['name'] == 'inject_test'
    assert isinstance(scheduled['input'], dict)
    assert 'tracing' in scheduled['input']
    assert scheduled['input']['a'] == 1


def test_runtime_restores_tracing_before_user_code(monkeypatch):
    import durabletask.worker as worker_mod

    monkeypatch.setattr(worker_mod, 'TaskHubGrpcWorker', _FakeWorker)

    seen: dict[str, Any] = {}

    class _TracingRuntime(RuntimeInterceptor):
        def execute_workflow(self, input, next):  # type: ignore[override]
            # no-op; real restoration is app concern; test just ensures input contains tracing
            return next(input)
        def execute_activity(self, input, next):  # type: ignore[override]
            return next(input)

    class _TracingClient2(ClientInterceptor):
        def schedule_new_workflow(self, input, next):  # type: ignore[override]
            tr = {'trace_id': 't1'}
            if isinstance(input.args, dict):
                input = type(input)(
                    workflow_name=input.workflow_name,
                    args={**input.args, 'tracing': tr},
                    instance_id=input.instance_id,
                    start_at=input.start_at,
                    reuse_id_policy=input.reuse_id_policy,
                )
            return next(input)

    rt = WorkflowRuntime(
        runtime_interceptors=[_TracingRuntime()],
    )

    @rt.workflow(name='w')
    def w(ctx, x):
        # The tracing should already be present in input
        assert isinstance(x, dict)
        assert 'tracing' in x
        seen['trace'] = x['tracing']
        yield 'noop'
        return 'ok'

    orch = rt._WorkflowRuntime__worker._registry.orchestrators['w']
    # Orchestrator input will have tracing injected via outbound when scheduled as a child or via client
    # Here, we directly pass the input simulating schedule with tracing present
    gen = orch(_FakeOrchestrationContext(), {'hello': 'world', 'tracing': {'trace_id': 't1'}})
    out = _drive_generator(gen, returned_value='noop')
    assert out == 'ok'
    assert seen['trace']['trace_id'] == 't1'
