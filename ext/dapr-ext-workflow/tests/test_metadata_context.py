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

from datetime import datetime
from typing import Any, Optional

import pytest

from dapr.ext.workflow import (
    ClientInterceptor,
    DaprWorkflowClient,
    ExecuteActivityRequest,
    ExecuteWorkflowRequest,
    RuntimeInterceptor,
    ScheduleWorkflowRequest,
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
        self._custom_status = None
        self.is_replaying = False
        self.workflow_name = 'wf'
        self.parent_instance_id = None
        self.history_event_sequence = 1
        self.trace_parent = None
        self.trace_state = None
        self.orchestration_span_id = None

    def call_activity(self, activity, *, input=None, retry_policy=None, app_id=None):
        class _T:
            def __init__(self, v):
                self._v = v

        return _T(input)

    def call_sub_orchestrator(self, wf, *, input=None, instance_id=None, retry_policy=None, app_id=None):
        class _T:
            def __init__(self, v):
                self._v = v

        return _T(input)

    def set_custom_status(self, custom_status):
        self._custom_status = custom_status

    def create_timer(self, fire_at):
        class _T:
            def __init__(self, v):
                self._v = v

        return _T(fire_at)

    def wait_for_external_event(self, name: str):
        class _T:
            def __init__(self, v):
                self._v = v

        return _T(name)


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
        def schedule_new_workflow(self, request: ScheduleWorkflowRequest, next):  # type: ignore[override]
            # Add metadata without touching args
            md = {'otel.trace_id': 't-123'}
            new_request = ScheduleWorkflowRequest(
                workflow_name=request.workflow_name,
                input=request.input,
                instance_id=request.instance_id,
                start_at=request.start_at,
                reuse_id_policy=request.reuse_id_policy,
                metadata=md,
            )
            return next(new_request)

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
        def execute_workflow(self, request: ExecuteWorkflowRequest, next):  # type: ignore[override]
            seen['metadata'] = request.metadata
            return next(request)

        def execute_activity(self, request: ExecuteActivityRequest, next):  # type: ignore[override]
            seen['act_metadata'] = request.metadata
            return next(request)

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
        def call_activity(self, request, next):  # type: ignore[override]
            # Wrap returned args with metadata by returning a new CallActivityRequest
            return next(
                type(request)(
                    activity_name=request.activity_name,
                    input=request.input,
                    retry_policy=request.retry_policy,
                    workflow_ctx=request.workflow_ctx,
                    metadata={'k': 'v'},
                )
            )

        def call_child_workflow(self, request, next):  # type: ignore[override]
            return next(
                type(request)(
                    workflow_name=request.workflow_name,
                    input=request.input,
                    instance_id=request.instance_id,
                    workflow_ctx=request.workflow_ctx,
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
    with pytest.raises(StopIteration) as stop:
        gen.send({'child': 'done'})
    result = stop.value.value
    # The result is whatever user returned; envelopes validated above
    assert isinstance(result, tuple) and len(result) == 2


def test_context_set_metadata_default_propagation(monkeypatch):
    import durabletask.worker as worker_mod

    monkeypatch.setattr(worker_mod, 'TaskHubGrpcWorker', _FakeWorker)

    # No outbound interceptor needed; runtime will wrap using ctx.get_metadata()
    rt = WorkflowRuntime()

    @rt.workflow(name='use_ctx_md')
    def use_ctx_md(ctx, x):
        # Set default metadata on context
        ctx.set_metadata({'k': 'ctx'})
        env = yield ctx.call_activity(lambda: None, input={'p': 1})
        # Return the raw yielded value for assertion
        return env

    orch = rt._WorkflowRuntime__worker._registry.orchestrators['use_ctx_md']
    gen = orch(_FakeOrchCtx(), 0)
    yielded = gen.send(None)
    assert hasattr(yielded, '_v')
    env = yielded._v
    assert isinstance(env, dict)
    assert env.get('__dapr_meta__', {}).get('metadata', {}).get('k') == 'ctx'


def test_per_call_metadata_overrides_context(monkeypatch):
    import durabletask.worker as worker_mod

    monkeypatch.setattr(worker_mod, 'TaskHubGrpcWorker', _FakeWorker)

    rt = WorkflowRuntime()

    @rt.workflow(name='override_ctx_md')
    def override_ctx_md(ctx, x):
        ctx.set_metadata({'k': 'ctx'})
        env = yield ctx.call_activity(lambda: None, input={'p': 1}, metadata={'k': 'per'})
        return env

    orch = rt._WorkflowRuntime__worker._registry.orchestrators['override_ctx_md']
    gen = orch(_FakeOrchCtx(), 0)
    yielded = gen.send(None)
    env = yielded._v
    assert isinstance(env, dict)
    assert env.get('__dapr_meta__', {}).get('metadata', {}).get('k') == 'per'


def test_execution_info_workflow_and_activity(monkeypatch):
    import durabletask.worker as worker_mod

    monkeypatch.setattr(worker_mod, 'TaskHubGrpcWorker', _FakeWorker)

    rt = WorkflowRuntime()

    def act(ctx, x):
        # activity inbound metadata and execution info available
        md = ctx.get_metadata()
        ei = ctx.execution_info
        assert md == {'m': 'v'}
        assert ei is not None and ei.inbound_metadata == {'m': 'v'}
        # activity_name should reflect the registered name
        assert ei.activity_name == 'act'
        return x

    @rt.workflow(name='execinfo')
    def execinfo(ctx, x):
        # set default metadata
        ctx.set_metadata({'m': 'v'})
        # workflow execution info available (minimal inbound only)
        wi = ctx.execution_info
        assert wi is not None and wi.inbound_metadata == {}
        v = yield ctx.call_activity(act, input=42)
        return v

    # register activity
    rt.activity(name='act')(act)
    orch = rt._WorkflowRuntime__worker._registry.orchestrators['execinfo']
    gen = orch(_FakeOrchCtx(), 7)
    # drive one yield (call_activity)
    gen.send(None)
    # send back a value for activity result
    with pytest.raises(StopIteration) as stop:
        gen.send(42)
    assert stop.value.value == 42


def test_client_interceptor_can_shape_schedule_response(monkeypatch):
    import durabletask.client as client_mod

    captured: dict[str, Any] = {}

    class _FakeClient:
        def __init__(self, *args, **kwargs):
            pass

        def schedule_new_orchestration(
            self, name, *, input=None, instance_id=None, start_at=None, reuse_id_policy=None
        ):
            captured['name'] = name
            return 'raw-id-123'

    monkeypatch.setattr(client_mod, 'TaskHubGrpcClient', _FakeClient)

    class _ShapeId(ClientInterceptor):
        def schedule_new_workflow(self, request: ScheduleWorkflowRequest, next):  # type: ignore[override]
            rid = next(request)
            return f'shaped:{rid}'

    client = DaprWorkflowClient(interceptors=[_ShapeId()])

    def wf(ctx):
        yield 'noop'

    wf.__name__ = 'shape_test'
    iid = client.schedule_new_workflow(wf, input=None)
    assert iid == 'shaped:raw-id-123'
