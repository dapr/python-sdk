# -*- coding: utf-8 -*-

"""
Interceptor tests for Dapr WorkflowRuntime.

This replaces legacy middleware-hook tests.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

import pytest

from dapr.ext.workflow import RuntimeInterceptor, WorkflowRuntime


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


class _RecorderInterceptor(RuntimeInterceptor):
    def __init__(self, events: list[str], label: str):
        self.events = events
        self.label = label

    def execute_workflow(self, input, next):  # type: ignore[override]
        self.events.append(f'{self.label}:wf_enter:{input.input!r}')
        ret = next(input)
        self.events.append(f'{self.label}:wf_ret_type:{ret.__class__.__name__}')
        return ret

    def execute_activity(self, input, next):  # type: ignore[override]
        self.events.append(f'{self.label}:act_enter:{input.input!r}')
        res = next(input)
        self.events.append(f'{self.label}:act_exit:{res!r}')
        return res


def test_generator_workflow_hooks_sequence(monkeypatch):
    import durabletask.worker as worker_mod

    monkeypatch.setattr(worker_mod, 'TaskHubGrpcWorker', _FakeWorker)

    events: list[str] = []
    ic = _RecorderInterceptor(events, 'mw')
    rt = WorkflowRuntime(interceptors=[ic])

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
    # Interceptors run once around the workflow entry; they return a generator to the runtime
    assert events[0] == 'mw:wf_enter:10'
    assert events[1].startswith('mw:wf_ret_type:')


def test_async_workflow_hooks_called(monkeypatch):
    import durabletask.worker as worker_mod

    monkeypatch.setattr(worker_mod, 'TaskHubGrpcWorker', _FakeWorker)

    events: list[str] = []
    ic = _RecorderInterceptor(events, 'mw')
    rt = WorkflowRuntime(interceptors=[ic])

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
    # For async workflow, interceptor sees entry and a generator return type
    assert events[0] == 'mw:wf_enter:41'
    assert events[1].startswith('mw:wf_ret_type:')


def test_activity_hooks_and_policy(monkeypatch):
    import durabletask.worker as worker_mod

    monkeypatch.setattr(worker_mod, 'TaskHubGrpcWorker', _FakeWorker)

    events: list[str] = []

    class _ExplodingActivity(RuntimeInterceptor):
        def execute_activity(self, input, next):  # type: ignore[override]
            raise RuntimeError('boom')
        def execute_workflow(self, input, next):  # type: ignore[override]
            return next(input)

    # Continue-on-error policy
    rt = WorkflowRuntime(interceptors=[_RecorderInterceptor(events, 'mw'), _ExplodingActivity()])

    @rt.activity(name='double')
    def double(ctx, x: int) -> int:
        return x * 2

    reg = rt._WorkflowRuntime__worker._registry
    act = reg.activities['double']
    # Error in interceptor bubbles up
    with pytest.raises(RuntimeError):
        act(_FakeActivityContext(), 5)


