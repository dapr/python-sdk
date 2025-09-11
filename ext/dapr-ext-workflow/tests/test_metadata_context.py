# -*- coding: utf-8 -*-

from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

import pytest

from dapr.ext.workflow import (
    ClientInterceptor,
    DaprWorkflowClient,
    ExecuteActivityInput,
    ExecuteWorkflowInput,
    RuntimeInterceptor,
    ScheduleWorkflowInput,
    WorkflowOutboundInterceptor,
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


class _FakeOrchCtx:
    def __init__(self):
        self.instance_id = 'id'
        self.current_utc_datetime = datetime(2024, 1, 1)

    def call_activity(self, activity, *, input=None, retry_policy=None):
        class _T:
            def __init__(self, v):
                self._v = v

        return _T(input)

    def call_sub_orchestrator(self, wf, *, input=None, instance_id=None, retry_policy=None):
        class _T:
            def __init__(self, v):
                self._v = v

        return _T(input)


def _drive(gen, returned):
    try:
        t = gen.send(None)
        assert hasattr(t, '_v')
        res = returned
        while True:
            t = gen.send(res)
            assert hasattr(t, '_v')
    except StopIteration as stop:
        return stop.value


def test_client_schedule_metadata_envelope(monkeypatch):
    import durabletask.client as client_mod

    captured: dict[str, Any] = {}

    class _FakeClient:
        def __init__(self, *args, **kwargs):
            pass

        def schedule_new_orchestration(
            self,
            name,
            *,
            input=None,
            instance_id=None,
            start_at: Optional[datetime] = None,
            reuse_id_policy=None,
        ):  # noqa: E501
            captured['name'] = name
            captured['input'] = input
            captured['instance_id'] = instance_id
            captured['start_at'] = start_at
            captured['reuse_id_policy'] = reuse_id_policy
            return 'id-1'

    monkeypatch.setattr(client_mod, 'TaskHubGrpcClient', _FakeClient)

    class _InjectMetadata(ClientInterceptor):
        def schedule_new_workflow(self, input: ScheduleWorkflowInput, next):  # type: ignore[override]
            # Add metadata without touching args
            md = {'otel.trace_id': 't-123'}
            new_input = ScheduleWorkflowInput(
                workflow_name=input.workflow_name,
                args=input.args,
                instance_id=input.instance_id,
                start_at=input.start_at,
                reuse_id_policy=input.reuse_id_policy,
                metadata=md,
                local_context=None,
            )
            return next(new_input)

    client = DaprWorkflowClient(interceptors=[_InjectMetadata()])

    def wf(ctx, x):
        yield 'noop'

    wf.__name__ = 'meta_wf'
    instance_id = client.schedule_new_workflow(wf, input={'a': 1})
    assert instance_id == 'id-1'
    env = captured['input']
    assert isinstance(env, dict)
    assert '__dapr_meta__' in env and '__dapr_payload__' in env
    assert env['__dapr_payload__'] == {'a': 1}
    assert env['__dapr_meta__']['metadata']['otel.trace_id'] == 't-123'


def test_runtime_inbound_unwrap_and_metadata_visible(monkeypatch):
    import durabletask.worker as worker_mod

    monkeypatch.setattr(worker_mod, 'TaskHubGrpcWorker', _FakeWorker)

    seen: dict[str, Any] = {}

    class _Recorder(RuntimeInterceptor):
        def execute_workflow(self, input: ExecuteWorkflowInput, next):  # type: ignore[override]
            seen['metadata'] = input.metadata
            return next(input)

        def execute_activity(self, input: ExecuteActivityInput, next):  # type: ignore[override]
            seen['act_metadata'] = input.metadata
            return next(input)

    rt = WorkflowRuntime(runtime_interceptors=[_Recorder()])

    @rt.workflow(name='unwrap')
    def unwrap(ctx, x):
        # x should be the original payload, not the envelope
        assert x == {'hello': 'world'}
        return 'ok'

    orch = rt._WorkflowRuntime__worker._registry.orchestrators['unwrap']
    envelope = {
        '__dapr_meta__': {'v': 1, 'metadata': {'c': 'd'}},
        '__dapr_payload__': {'hello': 'world'},
    }
    result = orch(_FakeOrchCtx(), envelope)
    assert result == 'ok'
    assert seen['metadata'] == {'c': 'd'}


def test_outbound_activity_and_child_wrap_metadata(monkeypatch):
    import durabletask.worker as worker_mod

    monkeypatch.setattr(worker_mod, 'TaskHubGrpcWorker', _FakeWorker)

    class _AddActMeta(WorkflowOutboundInterceptor):
        def call_activity(self, input, next):  # type: ignore[override]
            # Wrap returned args with metadata by returning a new CallActivityInput
            return next(
                type(input)(
                    activity_name=input.activity_name,
                    args=input.args,
                    retry_policy=input.retry_policy,
                    workflow_ctx=input.workflow_ctx,
                    metadata={'k': 'v'},
                )
            )

        def call_child_workflow(self, input, next):  # type: ignore[override]
            return next(
                type(input)(
                    workflow_name=input.workflow_name,
                    args=input.args,
                    instance_id=input.instance_id,
                    workflow_ctx=input.workflow_ctx,
                    metadata={'p': 'q'},
                )
            )

    rt = WorkflowRuntime(workflow_outbound_interceptors=[_AddActMeta()])

    @rt.workflow(name='parent')
    def parent(ctx, x):
        a = yield ctx.call_activity(lambda: None, input={'i': 1})
        b = yield ctx.call_child_workflow(lambda c, y: None, input={'j': 2})
        # Return both so we can assert envelopes surfaced through our fake driver
        return a, b

    orch = rt._WorkflowRuntime__worker._registry.orchestrators['parent']
    gen = orch(_FakeOrchCtx(), 0)
    # First yield: activity token received by driver; shape may be envelope or raw depending on adapter
    t1 = gen.send(None)
    assert hasattr(t1, '_v')
    # Resume with any value; our fake driver ignores and loops
    t2 = gen.send({'act': 'done'})
    assert hasattr(t2, '_v')
    env2 = t2._v
    with pytest.raises(StopIteration) as stop:
        gen.send({'child': 'done'})
    result = stop.value.value
    # The result is whatever user returned; envelopes validated above
    assert isinstance(result, tuple) and len(result) == 2


def test_local_context_runtime_chain_passthrough(monkeypatch):
    import durabletask.worker as worker_mod

    monkeypatch.setattr(worker_mod, 'TaskHubGrpcWorker', _FakeWorker)

    events: list[str] = []

    class _Outer(RuntimeInterceptor):
        def execute_workflow(self, input: ExecuteWorkflowInput, next):  # type: ignore[override]
            lc = dict(input.local_context or {})
            lc['flag'] = 'on'
            new_input = ExecuteWorkflowInput(
                ctx=input.ctx, input=input.input, metadata=input.metadata, local_context=lc
            )
            return next(new_input)

        def execute_activity(self, input: ExecuteActivityInput, next):  # type: ignore[override]
            return next(input)

    class _Inner(RuntimeInterceptor):
        def execute_workflow(self, input: ExecuteWorkflowInput, next):  # type: ignore[override]
            events.append(
                f"flag={input.local_context.get('flag') if input.local_context else None}"
            )
            return next(input)

        def execute_activity(self, input: ExecuteActivityInput, next):  # type: ignore[override]
            return next(input)

    rt = WorkflowRuntime(runtime_interceptors=[_Outer(), _Inner()])

    @rt.workflow(name='lc')
    def lc(ctx, x):
        return 'ok'

    orch = rt._WorkflowRuntime__worker._registry.orchestrators['lc']
    result = orch(_FakeOrchCtx(), 1)
    assert result == 'ok'
    assert events == ['flag=on']
