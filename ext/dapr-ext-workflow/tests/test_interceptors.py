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

from typing import Any

import pytest

from dapr.ext.workflow import RuntimeInterceptor, WorkflowRuntime

from ._fakes import make_act_ctx as _make_act_ctx
from ._fakes import make_orch_ctx as _make_orch_ctx

"""
Comprehensive inbound interceptor tests for Dapr WorkflowRuntime.

Tests the current interceptor system for runtime-side workflow and activity execution.
"""


"""
Runtime interceptor chain tests for `WorkflowRuntime`.

This suite intentionally uses a fake worker/registry to validate interceptor composition
without requiring a sidecar. It focuses on the "why" behind runtime interceptors:

- Ensure `execute_workflow` and `execute_activity` hooks compose in order and are
  invoked exactly once around workflow entry/activity execution.
- Cover both generator-based and async workflows, asserting the chain returns a
  generator to the runtime (rather than iterating it), preserving send()/throw()
  semantics during orchestration replay.
- Keep signal-to-noise high for failures in chain logic independent of gRPC/sidecar.

These tests complement outbound/client interceptor tests and e2e tests by providing
fast, deterministic coverage of the chaining behavior and generator handling rules.
"""


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


class _RecorderInterceptor(RuntimeInterceptor):
    def __init__(self, events: list[str], label: str):
        self.events = events
        self.label = label

    def execute_workflow(self, request, next):  # type: ignore[override]
        self.events.append(f'{self.label}:wf_enter:{request.input!r}')
        ret = next(request)
        self.events.append(f'{self.label}:wf_ret_type:{ret.__class__.__name__}')
        return ret

    def execute_activity(self, request, next):  # type: ignore[override]
        self.events.append(f'{self.label}:act_enter:{request.input!r}')
        res = next(request)
        self.events.append(f'{self.label}:act_exit:{res!r}')
        return res


def test_generator_workflow_hooks_sequence(monkeypatch):
    import durabletask.worker as worker_mod

    monkeypatch.setattr(worker_mod, 'TaskHubGrpcWorker', _FakeWorker)

    events: list[str] = []
    ic = _RecorderInterceptor(events, 'mw')
    rt = WorkflowRuntime(runtime_interceptors=[ic])

    @rt.workflow(name='gen')
    def gen(ctx, x: int):
        v = yield 'A'
        v2 = yield 'B'
        return (x, v, v2)

    # Drive the registered orchestrator
    reg = rt._WorkflowRuntime__worker._registry
    orch = reg.orchestrators['gen']
    gen_driver = orch(_make_orch_ctx(), 10)
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
    rt = WorkflowRuntime(runtime_interceptors=[ic])

    @rt.workflow(name='awf')
    async def awf(ctx, x: int):
        # No awaits to keep the driver simple
        return x + 1

    reg = rt._WorkflowRuntime__worker._registry
    orch = reg.orchestrators['awf']
    gen_orch = orch(_make_orch_ctx(), 41)
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
        def execute_activity(self, request, next):  # type: ignore[override]
            raise RuntimeError('boom')

        def execute_workflow(self, request, next):  # type: ignore[override]
            return next(request)

    # Continue-on-error policy
    rt = WorkflowRuntime(
        runtime_interceptors=[_RecorderInterceptor(events, 'mw'), _ExplodingActivity()]
    )

    @rt.activity(name='double')
    def double(ctx, x: int) -> int:
        return x * 2

    reg = rt._WorkflowRuntime__worker._registry
    act = reg.activities['double']
    # Error in interceptor bubbles up
    with pytest.raises(RuntimeError):
        act(_make_act_ctx(), 5)
