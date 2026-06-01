import time
from unittest.mock import Mock

import grpc
import pytest
from dapr.ext.workflow._durabletask.client import TaskHubGrpcClient


@pytest.mark.parametrize('timeout', [None, 0, 5])
def test_wait_for_orchestration_start_timeout(timeout):
    instance_id = 'test-instance'

    from dapr.ext.workflow._durabletask.internal.protos import (
        ORCHESTRATION_STATUS_RUNNING,
        GetInstanceResponse,
        WorkflowState,
    )

    response = GetInstanceResponse()
    state = WorkflowState()
    state.instanceId = instance_id
    state.workflowStatus = ORCHESTRATION_STATUS_RUNNING
    response.workflowState.CopyFrom(state)

    c = TaskHubGrpcClient()
    c._stub = Mock()
    c._stub.WaitForInstanceStart.return_value = response

    grpc_timeout = None if timeout is None else timeout
    c.wait_for_orchestration_start(instance_id, timeout=grpc_timeout)

    # Verify WaitForInstanceStart was called with timeout=None
    c._stub.WaitForInstanceStart.assert_called_once()
    _, kwargs = c._stub.WaitForInstanceStart.call_args
    if timeout is None or timeout == 0:
        assert kwargs.get('timeout') is None
    else:
        assert kwargs.get('timeout') == timeout


@pytest.mark.parametrize('timeout', [None, 0, 5])
def test_wait_for_orchestration_completion_timeout(timeout):
    instance_id = 'test-instance'

    from dapr.ext.workflow._durabletask.internal.protos import (
        ORCHESTRATION_STATUS_COMPLETED,
        GetInstanceResponse,
        WorkflowState,
    )

    response = GetInstanceResponse()
    state = WorkflowState()
    state.instanceId = instance_id
    state.workflowStatus = ORCHESTRATION_STATUS_COMPLETED
    response.workflowState.CopyFrom(state)

    c = TaskHubGrpcClient()
    c._stub = Mock()
    c._stub.WaitForInstanceCompletion.return_value = response

    grpc_timeout = None if timeout is None else timeout
    c.wait_for_orchestration_completion(instance_id, timeout=grpc_timeout)

    # Verify WaitForInstanceStart was called with timeout=None
    c._stub.WaitForInstanceCompletion.assert_called_once()
    _, kwargs = c._stub.WaitForInstanceCompletion.call_args
    if timeout is None or timeout == 0:
        assert kwargs.get('timeout') is None
    else:
        assert kwargs.get('timeout') == timeout


def _make_rpc_error(code: grpc.StatusCode) -> grpc.RpcError:
    err = grpc.RpcError()
    err.code = lambda: code  # type: ignore[method-assign]
    err.details = lambda: f'simulated {code.name}'  # type: ignore[method-assign]
    return err


@pytest.mark.parametrize(
    'transient_code', [grpc.StatusCode.FAILED_PRECONDITION, grpc.StatusCode.UNAVAILABLE]
)
def test_wait_for_orchestration_start_retries_transient_then_succeeds(transient_code, monkeypatch):
    """Transient gRPC error on the first call → backoff → next call succeeds."""
    instance_id = 'test-instance'

    from dapr.ext.workflow._durabletask.internal.protos import (
        ORCHESTRATION_STATUS_RUNNING,
        GetInstanceResponse,
        WorkflowState,
    )

    response = GetInstanceResponse()
    state = WorkflowState()
    state.instanceId = instance_id
    state.workflowStatus = ORCHESTRATION_STATUS_RUNNING
    response.workflowState.CopyFrom(state)

    sleeps = []
    monkeypatch.setattr(
        'dapr.ext.workflow._durabletask.client.time.sleep', lambda s: sleeps.append(s)
    )

    calls = {'n': 0}

    def fake_call(*args, **kwargs):
        calls['n'] += 1
        if calls['n'] == 1:
            raise _make_rpc_error(transient_code)
        return response

    c = TaskHubGrpcClient()
    c._stub = Mock()
    c._stub.WaitForInstanceStart.side_effect = fake_call

    # The point of this test is the retry behavior, not the response payload —
    # the second call returns successfully (no exception), the first transient
    # is absorbed, and exactly one backoff sleep happens between them.
    c.wait_for_orchestration_start(instance_id, timeout=10)
    assert calls['n'] == 2
    assert len(sleeps) == 1 and sleeps[0] > 0


def test_wait_for_orchestration_start_transient_exhaustion_raises_timeout(monkeypatch):
    """Transient gRPC errors keep returning until the user budget runs out
    → public TimeoutError, not the raw RpcError."""
    instance_id = 'test-instance'

    # Advance monotonic time on every call so the deadline is reached quickly.
    fake_time = [0.0]

    def fake_monotonic():
        fake_time[0] += 0.6  # 0.0, 0.6, 1.2, ...
        return fake_time[0]

    monkeypatch.setattr('dapr.ext.workflow._durabletask.client.time.monotonic', fake_monotonic)
    monkeypatch.setattr('dapr.ext.workflow._durabletask.client.time.sleep', lambda s: None)

    c = TaskHubGrpcClient()
    c._stub = Mock()
    c._stub.WaitForInstanceStart.side_effect = _make_rpc_error(grpc.StatusCode.UNAVAILABLE)

    with pytest.raises(TimeoutError):
        c.wait_for_orchestration_start(instance_id, timeout=1)


def test_wait_for_orchestration_start_non_transient_propagates(monkeypatch):
    """Non-transient gRPC errors must NOT be retried — propagate directly."""
    instance_id = 'test-instance'
    monkeypatch.setattr(time, 'sleep', lambda s: None)

    c = TaskHubGrpcClient()
    c._stub = Mock()
    c._stub.WaitForInstanceStart.side_effect = _make_rpc_error(grpc.StatusCode.PERMISSION_DENIED)

    with pytest.raises(grpc.RpcError):
        c.wait_for_orchestration_start(instance_id, timeout=10)
    assert c._stub.WaitForInstanceStart.call_count == 1


def test_wait_for_orchestration_start_unbounded_transient_gives_up_with_rpc_error(monkeypatch):
    """With timeout=0 (unbounded), persistent transient errors are retried only
    for the grace window, then the original RpcError propagates — NOT a hang and
    NOT a TimeoutError, preserving the pre-retry contract that timeout=0 surfaces
    the gRPC error rather than TimeoutError."""
    instance_id = 'test-instance'

    # Advance well past _MAX_TRANSIENT_RETRY_SECONDS on each transient so the
    # grace window is exhausted within a couple of retries.
    fake_time = [0.0]

    def fake_monotonic():
        fake_time[0] += 20.0  # 20, 40, 60, ... — anchors at 20, deadline 50
        return fake_time[0]

    monkeypatch.setattr('dapr.ext.workflow._durabletask.client.time.monotonic', fake_monotonic)
    monkeypatch.setattr('dapr.ext.workflow._durabletask.client.time.sleep', lambda s: None)

    c = TaskHubGrpcClient()
    c._stub = Mock()
    c._stub.WaitForInstanceStart.side_effect = _make_rpc_error(grpc.StatusCode.UNAVAILABLE)

    with pytest.raises(grpc.RpcError) as exc_info:
        c.wait_for_orchestration_start(instance_id, timeout=0)
    assert not isinstance(exc_info.value, TimeoutError)
    # Retried at least once before giving up (proves it didn't fail-fast like the
    # non-transient path, and didn't loop forever).
    assert c._stub.WaitForInstanceStart.call_count >= 2
