# -*- coding: utf-8 -*-

from __future__ import annotations

from dapr.ext.workflow import WorkflowOutboundInterceptor, WorkflowRuntime


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

    def call_activity(self, activity, *, input=None, retry_policy=None):
        # return input back for assertion through driver
        class _T:
            def __init__(self, v):
                self._v = v

        return _T(input)

    def call_sub_orchestrator(self, wf, *, input=None, instance_id=None, retry_policy=None):
        class _T:
            def __init__(self, v):
                self._v = v

        return _T(input)


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
    def call_activity(self, input, next):  # type: ignore[override]
        x = input.args
        if x is None:
            input = type(input)(
                activity_name=input.activity_name,
                args={'tracing': 'T'},
                retry_policy=input.retry_policy,
            )
        elif isinstance(x, dict):
            out = dict(x)
            out.setdefault('tracing', 'T')
            input = type(input)(
                activity_name=input.activity_name, args=out, retry_policy=input.retry_policy
            )
        return next(input)

    def call_child_workflow(self, input, next):  # type: ignore[override]
        return next(
            type(input)(
                workflow_name=input.workflow_name,
                args={'child': input.args},
                instance_id=input.instance_id,
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
