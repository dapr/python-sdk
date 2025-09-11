# -*- coding: utf-8 -*-

"""
Comprehensive inbound interceptor tests for Dapr WorkflowRuntime.

Tests the current interceptor system for runtime-side workflow and activity execution.
"""

from __future__ import annotations

import asyncio
from datetime import datetime
from typing import Any

import pytest

from dapr.ext.workflow import (
    ExecuteActivityInput,
    ExecuteWorkflowInput,
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


class _FakeActivityContext:
    def __init__(self):
        self.orchestration_id = 'wf-1'
        self.task_id = 1


class _TracingInterceptor(RuntimeInterceptor):
    """Interceptor that injects and restores trace context."""

    def __init__(self, events: list[str]):
        self.events = events

    def execute_workflow(self, input: ExecuteWorkflowInput, next):
        # Extract tracing from input
        tracing_data = None
        if isinstance(input.input, dict) and 'tracing' in input.input:
            tracing_data = input.input['tracing']
            self.events.append(f'wf_trace_restored:{tracing_data}')

        # Call next in chain
        result = next(input)

        if tracing_data:
            self.events.append(f'wf_trace_cleanup:{tracing_data}')

        return result

    def execute_activity(self, input: ExecuteActivityInput, next):
        # Extract tracing from input
        tracing_data = None
        if isinstance(input.input, dict) and 'tracing' in input.input:
            tracing_data = input.input['tracing']
            self.events.append(f'act_trace_restored:{tracing_data}')

        # Call next in chain
        result = next(input)

        if tracing_data:
            self.events.append(f'act_trace_cleanup:{tracing_data}')

        return result


class _LoggingInterceptor(RuntimeInterceptor):
    """Interceptor that logs workflow and activity execution."""

    def __init__(self, events: list[str], label: str):
        self.events = events
        self.label = label

    def execute_workflow(self, input: ExecuteWorkflowInput, next):
        self.events.append(f'{self.label}:wf_start:{input.input!r}')
        try:
            result = next(input)
            self.events.append(f'{self.label}:wf_complete:{result!r}')
            return result
        except Exception as e:
            self.events.append(f'{self.label}:wf_error:{type(e).__name__}')
            raise

    def execute_activity(self, input: ExecuteActivityInput, next):
        self.events.append(f'{self.label}:act_start:{input.input!r}')
        try:
            result = next(input)
            self.events.append(f'{self.label}:act_complete:{result!r}')
            return result
        except Exception as e:
            self.events.append(f'{self.label}:act_error:{type(e).__name__}')
            raise


class _ValidationInterceptor(RuntimeInterceptor):
    """Interceptor that validates inputs and outputs."""

    def __init__(self, events: list[str]):
        self.events = events

    def execute_workflow(self, input: ExecuteWorkflowInput, next):
        # Validate input
        if isinstance(input.input, dict) and input.input.get('invalid'):
            self.events.append('wf_validation_failed')
            raise ValueError('Invalid workflow input')

        self.events.append('wf_validation_passed')
        result = next(input)

        # Validate output
        if isinstance(result, dict) and result.get('invalid_output'):
            self.events.append('wf_output_validation_failed')
            raise ValueError('Invalid workflow output')

        self.events.append('wf_output_validation_passed')
        return result

    def execute_activity(self, input: ExecuteActivityInput, next):
        # Validate input
        if isinstance(input.input, dict) and input.input.get('invalid'):
            self.events.append('act_validation_failed')
            raise ValueError('Invalid activity input')

        self.events.append('act_validation_passed')
        result = next(input)

        # Validate output
        if isinstance(result, str) and 'invalid' in result:
            self.events.append('act_output_validation_failed')
            raise ValueError('Invalid activity output')

        self.events.append('act_output_validation_passed')
        return result


def test_single_interceptor_workflow_execution(monkeypatch):
    """Test single interceptor around workflow execution."""
    import durabletask.worker as worker_mod

    monkeypatch.setattr(worker_mod, 'TaskHubGrpcWorker', _FakeWorker)

    events: list[str] = []
    logging_interceptor = _LoggingInterceptor(events, 'log')
    rt = WorkflowRuntime(runtime_interceptors=[logging_interceptor])

    @rt.workflow(name='simple')
    def simple(ctx, x: int):
        return x * 2

    reg = rt._WorkflowRuntime__worker._registry
    orch = reg.orchestrators['simple']
    result = orch(_FakeOrchestrationContext(), 5)

    # For non-generator workflows, the result is returned directly
    assert result == 10
    assert events == [
        'log:wf_start:5',
        'log:wf_complete:10',
    ]


def test_single_interceptor_activity_execution(monkeypatch):
    """Test single interceptor around activity execution."""
    import durabletask.worker as worker_mod

    monkeypatch.setattr(worker_mod, 'TaskHubGrpcWorker', _FakeWorker)

    events: list[str] = []
    logging_interceptor = _LoggingInterceptor(events, 'log')
    rt = WorkflowRuntime(runtime_interceptors=[logging_interceptor])

    @rt.activity(name='double')
    def double(ctx, x: int) -> int:
        return x * 2

    reg = rt._WorkflowRuntime__worker._registry
    act = reg.activities['double']
    result = act(_FakeActivityContext(), 7)

    assert result == 14
    assert events == [
        'log:act_start:7',
        'log:act_complete:14',
    ]


def test_multiple_interceptors_execution_order(monkeypatch):
    """Test multiple interceptors execute in correct order."""
    import durabletask.worker as worker_mod

    monkeypatch.setattr(worker_mod, 'TaskHubGrpcWorker', _FakeWorker)

    events: list[str] = []
    outer_interceptor = _LoggingInterceptor(events, 'outer')
    inner_interceptor = _LoggingInterceptor(events, 'inner')

    # First interceptor in list is outermost
    rt = WorkflowRuntime(runtime_interceptors=[outer_interceptor, inner_interceptor])

    @rt.workflow(name='ordered')
    def ordered(ctx, x: int):
        return x + 1

    reg = rt._WorkflowRuntime__worker._registry
    orch = reg.orchestrators['ordered']
    result = orch(_FakeOrchestrationContext(), 3)

    assert result == 4
    # Outer interceptor enters first, exits last (stack semantics)
    assert events == [
        'outer:wf_start:3',
        'inner:wf_start:3',
        'inner:wf_complete:4',
        'outer:wf_complete:4',
    ]


def test_tracing_interceptor_context_restoration(monkeypatch):
    """Test tracing interceptor properly handles trace context."""
    import durabletask.worker as worker_mod

    monkeypatch.setattr(worker_mod, 'TaskHubGrpcWorker', _FakeWorker)

    events: list[str] = []
    tracing_interceptor = _TracingInterceptor(events)
    rt = WorkflowRuntime(runtime_interceptors=[tracing_interceptor])

    @rt.workflow(name='traced')
    def traced(ctx, input_data):
        # Workflow can access the trace context that was restored
        return {'result': input_data.get('value', 0) * 2}

    reg = rt._WorkflowRuntime__worker._registry
    orch = reg.orchestrators['traced']

    # Input with tracing data
    input_with_trace = {
        'value': 5,
        'tracing': {'trace_id': 'abc123', 'span_id': 'def456'}
    }

    result = orch(_FakeOrchestrationContext(), input_with_trace)

    assert result == {'result': 10}
    assert events == [
        "wf_trace_restored:{'trace_id': 'abc123', 'span_id': 'def456'}",
        "wf_trace_cleanup:{'trace_id': 'abc123', 'span_id': 'def456'}",
    ]


def test_validation_interceptor_input_validation(monkeypatch):
    """Test validation interceptor catches invalid inputs."""
    import durabletask.worker as worker_mod

    monkeypatch.setattr(worker_mod, 'TaskHubGrpcWorker', _FakeWorker)

    events: list[str] = []
    validation_interceptor = _ValidationInterceptor(events)
    rt = WorkflowRuntime(runtime_interceptors=[validation_interceptor])

    @rt.workflow(name='validated')
    def validated(ctx, input_data):
        return {'result': 'ok'}

    reg = rt._WorkflowRuntime__worker._registry
    orch = reg.orchestrators['validated']

    # Test valid input
    result = orch(_FakeOrchestrationContext(), {'value': 5})

    assert result == {'result': 'ok'}
    assert 'wf_validation_passed' in events
    assert 'wf_output_validation_passed' in events

    # Test invalid input
    events.clear()

    with pytest.raises(ValueError, match='Invalid workflow input'):
        orch(_FakeOrchestrationContext(), {'invalid': True})

    assert 'wf_validation_failed' in events


def test_interceptor_error_handling_workflow(monkeypatch):
    """Test interceptor properly handles workflow errors."""
    import durabletask.worker as worker_mod

    monkeypatch.setattr(worker_mod, 'TaskHubGrpcWorker', _FakeWorker)

    events: list[str] = []
    logging_interceptor = _LoggingInterceptor(events, 'log')
    rt = WorkflowRuntime(runtime_interceptors=[logging_interceptor])

    @rt.workflow(name='error_wf')
    def error_wf(ctx, x: int):
        raise ValueError('workflow error')

    reg = rt._WorkflowRuntime__worker._registry
    orch = reg.orchestrators['error_wf']

    with pytest.raises(ValueError, match='workflow error'):
        orch(_FakeOrchestrationContext(), 1)

    assert events == [
        'log:wf_start:1',
        'log:wf_error:ValueError',
    ]


def test_interceptor_error_handling_activity(monkeypatch):
    """Test interceptor properly handles activity errors."""
    import durabletask.worker as worker_mod

    monkeypatch.setattr(worker_mod, 'TaskHubGrpcWorker', _FakeWorker)

    events: list[str] = []
    logging_interceptor = _LoggingInterceptor(events, 'log')
    rt = WorkflowRuntime(runtime_interceptors=[logging_interceptor])

    @rt.activity(name='error_act')
    def error_act(ctx, x: int) -> int:
        raise RuntimeError('activity error')

    reg = rt._WorkflowRuntime__worker._registry
    act = reg.activities['error_act']

    with pytest.raises(RuntimeError, match='activity error'):
        act(_FakeActivityContext(), 5)

    assert events == [
        'log:act_start:5',
        'log:act_error:RuntimeError',
    ]


def test_async_workflow_with_interceptors(monkeypatch):
    """Test interceptors work with async workflows."""
    import durabletask.worker as worker_mod

    monkeypatch.setattr(worker_mod, 'TaskHubGrpcWorker', _FakeWorker)

    events: list[str] = []
    logging_interceptor = _LoggingInterceptor(events, 'log')
    rt = WorkflowRuntime(runtime_interceptors=[logging_interceptor])

    @rt.workflow(name='async_wf')
    async def async_wf(ctx, x: int):
        # Simple async workflow
        return x * 3

    reg = rt._WorkflowRuntime__worker._registry
    orch = reg.orchestrators['async_wf']
    gen_result = orch(_FakeOrchestrationContext(), 4)

    # Async workflows return a generator that needs to be driven
    with pytest.raises(StopIteration) as stop:
        next(gen_result)
    result = stop.value.value

    assert result == 12
    # The interceptor sees the generator being returned, not the final result
    assert events[0] == 'log:wf_start:4'
    assert 'log:wf_complete:' in events[1]  # The generator object is logged


def test_async_activity_with_interceptors(monkeypatch):
    """Test interceptors work with async activities."""
    import durabletask.worker as worker_mod

    monkeypatch.setattr(worker_mod, 'TaskHubGrpcWorker', _FakeWorker)

    events: list[str] = []
    logging_interceptor = _LoggingInterceptor(events, 'log')
    rt = WorkflowRuntime(runtime_interceptors=[logging_interceptor])

    @rt.activity(name='async_act')
    async def async_act(ctx, x: int) -> int:
        await asyncio.sleep(0)  # Simulate async work
        return x * 4

    reg = rt._WorkflowRuntime__worker._registry
    act = reg.activities['async_act']
    result = act(_FakeActivityContext(), 3)

    assert result == 12
    assert events == [
        'log:act_start:3',
        'log:act_complete:12',
    ]


def test_generator_workflow_with_interceptors(monkeypatch):
    """Test interceptors work with generator workflows."""
    import durabletask.worker as worker_mod

    monkeypatch.setattr(worker_mod, 'TaskHubGrpcWorker', _FakeWorker)

    events: list[str] = []
    logging_interceptor = _LoggingInterceptor(events, 'log')
    rt = WorkflowRuntime(runtime_interceptors=[logging_interceptor])

    @rt.workflow(name='gen_wf')
    def gen_wf(ctx, x: int):
        v1 = yield 'step1'
        v2 = yield 'step2'
        return (x, v1, v2)

    reg = rt._WorkflowRuntime__worker._registry
    orch = reg.orchestrators['gen_wf']
    gen_orch = orch(_FakeOrchestrationContext(), 1)

    # Drive the generator
    assert next(gen_orch) == 'step1'
    assert gen_orch.send('result1') == 'step2'
    with pytest.raises(StopIteration) as stop:
        gen_orch.send('result2')
    result = stop.value.value

    assert result == (1, 'result1', 'result2')
    # For generator workflows, interceptor sees the generator being returned
    assert events[0] == 'log:wf_start:1'
    assert 'log:wf_complete:' in events[1]  # The generator object is logged


def test_interceptor_chain_with_early_return(monkeypatch):
    """Test interceptor can modify or short-circuit execution."""
    import durabletask.worker as worker_mod

    monkeypatch.setattr(worker_mod, 'TaskHubGrpcWorker', _FakeWorker)

    events: list[str] = []

    class _ShortCircuitInterceptor(RuntimeInterceptor):
        def execute_workflow(self, input: ExecuteWorkflowInput, next):
            events.append('short_circuit_check')
            if isinstance(input.input, dict) and input.input.get('short_circuit'):
                events.append('short_circuited')
                return 'short_circuit_result'
            return next(input)

        def execute_activity(self, input: ExecuteActivityInput, next):
            return next(input)

    logging_interceptor = _LoggingInterceptor(events, 'log')
    short_circuit_interceptor = _ShortCircuitInterceptor()

    rt = WorkflowRuntime(runtime_interceptors=[short_circuit_interceptor, logging_interceptor])

    @rt.workflow(name='maybe_short')
    def maybe_short(ctx, input_data):
        return 'normal_result'

    reg = rt._WorkflowRuntime__worker._registry
    orch = reg.orchestrators['maybe_short']

    # Test normal execution
    result = orch(_FakeOrchestrationContext(), {'value': 5})

    assert result == 'normal_result'
    assert 'short_circuit_check' in events
    assert 'log:wf_start' in str(events)
    assert 'log:wf_complete' in str(events)

    # Test short-circuit execution
    events.clear()
    result = orch(_FakeOrchestrationContext(), {'short_circuit': True})

    assert result == 'short_circuit_result'
    assert 'short_circuit_check' in events
    assert 'short_circuited' in events
    # Logging interceptor should not be called when short-circuited
    assert 'log:wf_start' not in str(events)


def test_interceptor_input_transformation(monkeypatch):
    """Test interceptor can transform inputs before execution."""
    import durabletask.worker as worker_mod

    monkeypatch.setattr(worker_mod, 'TaskHubGrpcWorker', _FakeWorker)

    events: list[str] = []

    class _TransformInterceptor(RuntimeInterceptor):
        def execute_workflow(self, input: ExecuteWorkflowInput, next):
            # Transform input by adding metadata
            if isinstance(input.input, dict):
                transformed_input = {**input.input, 'interceptor_metadata': 'added'}
                new_input = ExecuteWorkflowInput(ctx=input.ctx, input=transformed_input)
                events.append(f'transformed_input:{transformed_input}')
                return next(new_input)
            return next(input)

        def execute_activity(self, input: ExecuteActivityInput, next):
            return next(input)

    transform_interceptor = _TransformInterceptor()
    rt = WorkflowRuntime(runtime_interceptors=[transform_interceptor])

    @rt.workflow(name='transform_test')
    def transform_test(ctx, input_data):
        # Workflow should see the transformed input
        return input_data

    reg = rt._WorkflowRuntime__worker._registry
    orch = reg.orchestrators['transform_test']
    result = orch(_FakeOrchestrationContext(), {'original': 'value'})

    # Result should include the interceptor metadata
    assert result == {'original': 'value', 'interceptor_metadata': 'added'}
    assert 'transformed_input:' in str(events)
