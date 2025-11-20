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

from dapr.ext.workflow import (
    BaseWorkflowOutboundInterceptor,
    WorkflowOutboundInterceptor,
    WorkflowRuntime,
)


class _FakeRegistry:
    def __init__(self):
        self.orchestrators = {}

    def add_named_orchestrator(self, name, fn):
        self.orchestrators[name] = fn


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
        self.current_utc_datetime = __import__('datetime').datetime(2024, 1, 1)
        self.is_replaying = False
        self._custom_status = None
        self.workflow_name = 'wf'
        self.parent_instance_id = None
        self.history_event_sequence = 1
        self.trace_parent = None
        self.trace_state = None
        self.orchestration_span_id = None
        self._continued_payload = None
        self.workflow_attempt = None

    def call_activity(self, activity, *, input=None, retry_policy=None, app_id=None):
        # return input back for assertion through driver
        class _T:
            def __init__(self, v):
                self._v = v

        return _T(input)

    def call_sub_orchestrator(
        self, wf, *, input=None, instance_id=None, retry_policy=None, app_id=None
    ):
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

    def continue_as_new(self, new_request, *, save_events: bool = False):
        # Record payload for assertions
        self._continued_payload = new_request


def drive(gen, returned):
    try:
        t = gen.send(None)
        assert hasattr(t, '_v')
        res = returned
        while True:
            t = gen.send(res)
            assert hasattr(t, '_v')
    except StopIteration as stop:
        return stop.value


class _InjectTrace(WorkflowOutboundInterceptor):
    def call_activity(self, request, next):  # type: ignore[override]
        x = request.input
        if x is None:
            request = type(request)(
                activity_name=request.activity_name,
                input={'tracing': 'T'},
                retry_policy=request.retry_policy,
            )
        elif isinstance(x, dict):
            out = dict(x)
            out.setdefault('tracing', 'T')
            request = type(request)(
                activity_name=request.activity_name, input=out, retry_policy=request.retry_policy
            )
        return next(request)

    def call_child_workflow(self, request, next):  # type: ignore[override]
        return next(
            type(request)(
                workflow_name=request.workflow_name,
                input={'child': request.input},
                instance_id=request.instance_id,
            )
        )


def test_outbound_activity_injection(monkeypatch):
    import durabletask.worker as worker_mod

    monkeypatch.setattr(worker_mod, 'TaskHubGrpcWorker', _FakeWorker)

    rt = WorkflowRuntime(workflow_outbound_interceptors=[_InjectTrace()])

    @rt.workflow(name='w')
    def w(ctx, x):
        # schedule an activity; runtime should pass transformed input to durable task
        y = yield ctx.call_activity(lambda: None, input={'a': 1})
        return y['tracing']

    orch = rt._WorkflowRuntime__worker._registry.orchestrators['w']
    gen = orch(_FakeOrchCtx(), 0)
    out = drive(gen, returned={'tracing': 'T', 'a': 1})
    assert out == 'T'


def test_outbound_child_injection(monkeypatch):
    import durabletask.worker as worker_mod

    monkeypatch.setattr(worker_mod, 'TaskHubGrpcWorker', _FakeWorker)

    rt = WorkflowRuntime(workflow_outbound_interceptors=[_InjectTrace()])

    def child(ctx, x):
        yield 'noop'

    @rt.workflow(name='parent')
    def parent(ctx, x):
        y = yield ctx.call_child_workflow(child, input={'b': 2})
        return y

    orch = rt._WorkflowRuntime__worker._registry.orchestrators['parent']
    gen = orch(_FakeOrchCtx(), 0)
    out = drive(gen, returned={'child': {'b': 2}})
    assert out == {'child': {'b': 2}}


def test_outbound_continue_as_new_injection(monkeypatch):
    import durabletask.worker as worker_mod

    monkeypatch.setattr(worker_mod, 'TaskHubGrpcWorker', _FakeWorker)

    class _InjectCAN(BaseWorkflowOutboundInterceptor):
        def continue_as_new(self, request, next):  # type: ignore[override]
            md = dict(request.metadata or {})
            md.setdefault('x', '1')
            request.metadata = md
            return next(request)

    rt = WorkflowRuntime(workflow_outbound_interceptors=[_InjectCAN()])

    @rt.workflow(name='w2')
    def w2(ctx, x):
        ctx.continue_as_new({'p': 1})
        return 'unreached'

    orch = rt._WorkflowRuntime__worker._registry.orchestrators['w2']
    fake = _FakeOrchCtx()
    _ = orch(fake, 0)
    # Verify envelope contains injected metadata
    assert isinstance(fake._continued_payload, dict)
    meta = fake._continued_payload.get('__dapr_meta__')
    payload = fake._continued_payload.get('__dapr_payload__')
    assert isinstance(meta, dict) and isinstance(payload, dict)
    assert meta.get('metadata', {}).get('x') == '1'
    assert payload == {'p': 1}
