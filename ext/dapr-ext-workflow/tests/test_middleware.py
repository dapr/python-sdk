# -*- coding: utf-8 -*-

"""
Middleware hook tests for Dapr WorkflowRuntime.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

import pytest

from dapr.ext.workflow import MiddlewarePolicy, RuntimeMiddleware, WorkflowRuntime


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
    def __init__(self):
        self.instance_id = 'wf-1'
        self.current_utc_datetime = datetime(2025, 1, 1)
        self.is_replaying = False


class _FakeActivityContext:
    def __init__(self):
        self.orchestration_id = 'wf-1'
        self.task_id = 1


class _RecorderMiddleware(RuntimeMiddleware):
    def __init__(self, events: list[str], label: str):
        self.events = events
        self.label = label

    # workflow
    def on_workflow_start(self, ctx, input):
        self.events.append(f'{self.label}:wf_start:{input!r}')

    def on_workflow_yield(self, ctx, yielded):
        # Orchestrator hooks must be synchronous
        self.events.append(f'{self.label}:wf_yield:{yielded!r}')

    def on_workflow_resume(self, ctx, resumed_value):
        self.events.append(f'{self.label}:wf_resume:{resumed_value!r}')

    def on_workflow_complete(self, ctx, result):
        self.events.append(f'{self.label}:wf_complete:{result!r}')

    def on_workflow_error(self, ctx, error: BaseException):
        self.events.append(f'{self.label}:wf_error:{type(error).__name__}')

    # activity
    async def on_activity_start(self, ctx, input):
        # Async hooks ARE awaited for activities
        self.events.append(f'{self.label}:act_start:{input!r}')

    def on_activity_complete(self, ctx, result):
        self.events.append(f'{self.label}:act_complete:{result!r}')

    def on_activity_error(self, ctx, error: BaseException):
        self.events.append(f'{self.label}:act_error:{type(error).__name__}')


def test_generator_workflow_hooks_sequence(monkeypatch):
    import durabletask.worker as worker_mod

    monkeypatch.setattr(worker_mod, 'TaskHubGrpcWorker', _FakeWorker)

    events: list[str] = []
    mw = _RecorderMiddleware(events, 'mw')
    rt = WorkflowRuntime(middleware=[mw])

    @rt.workflow(name='gen')
    def gen(ctx, x: int):
        v = yield 'A'
        v2 = yield 'B'
        return (x, v, v2)

    # Drive the registered orchestrator
    reg = rt._WorkflowRuntime__worker._registry
    orch = reg.orchestrators['gen']
    gen_driver = orch(_FakeOrchestrationContext(), 10)
    # Prime and run
    assert next(gen_driver) == 'A'
    assert gen_driver.send('ra') == 'B'
    with pytest.raises(StopIteration) as stop:
        gen_driver.send('rb')
    result = stop.value.value

    assert result == (10, 'ra', 'rb')
    assert events == [
        "mw:wf_start:10",
        "mw:wf_yield:'A'",
        "mw:wf_resume:'ra'",
        "mw:wf_yield:'B'",
        "mw:wf_resume:'rb'",
        "mw:wf_complete:(10, 'ra', 'rb')",
    ]


def test_async_workflow_hooks_called(monkeypatch):
    import durabletask.worker as worker_mod

    monkeypatch.setattr(worker_mod, 'TaskHubGrpcWorker', _FakeWorker)

    events: list[str] = []
    mw = _RecorderMiddleware(events, 'mw')
    rt = WorkflowRuntime(middleware=[mw])

    @rt.workflow(name='awf')
    async def awf(ctx, x: int):
        # No awaits to keep the driver simple
        return x + 1

    reg = rt._WorkflowRuntime__worker._registry
    orch = reg.orchestrators['awf']
    gen_orch = orch(_FakeOrchestrationContext(), 41)
    with pytest.raises(StopIteration) as stop:
        next(gen_orch)
    result = stop.value.value

    assert result == 42
    # For async workflow that completes synchronously, only start/complete fire
    assert events == [
        'mw:wf_start:41',
        'mw:wf_complete:42',
    ]


def test_activity_hooks_and_policy(monkeypatch):
    import durabletask.worker as worker_mod

    monkeypatch.setattr(worker_mod, 'TaskHubGrpcWorker', _FakeWorker)

    events: list[str] = []

    class _ExplodingStart(RuntimeMiddleware):
        def on_activity_start(self, ctx, input):  # type: ignore[override]
            raise RuntimeError('boom')

    # Continue-on-error policy
    rt = WorkflowRuntime(middleware=[_RecorderMiddleware(events, 'mw'), _ExplodingStart()])

    @rt.activity(name='double')
    def double(ctx, x: int) -> int:
        return x * 2

    reg = rt._WorkflowRuntime__worker._registry
    act = reg.activities['double']
    result = act(_FakeActivityContext(), 5)
    assert result == 10
    # Start error is swallowed; complete fires
    assert events[-1] == 'mw:act_complete:10'

    # Now raise-on-error policy
    events.clear()
    rt2 = WorkflowRuntime(middleware=[_ExplodingStart()], middleware_policy=MiddlewarePolicy.RAISE_ON_ERROR)

    @rt2.activity(name='double2')
    def double2(ctx, x: int) -> int:
        return x * 2

    reg2 = rt2._WorkflowRuntime__worker._registry
    act2 = reg2.activities['double2']
    with pytest.raises(RuntimeError):
        act2(_FakeActivityContext(), 6)


