import time
from typing import Optional
from unittest.mock import Mock

import grpc
import pytest

from dapr.ext.workflow._durabletask.client import OrchestrationStatus, TaskHubGrpcClient


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


def _make_rpc_error(code: grpc.StatusCode, details: Optional[str] = None) -> grpc.RpcError:
    err = grpc.RpcError()
    err.code = lambda: code  # type: ignore[method-assign]
    err.details = lambda: details if details is not None else f'simulated {code.name}'  # type: ignore[method-assign]
    return err


@pytest.mark.parametrize(
    'transient_code',
    [
        grpc.StatusCode.CANCELLED,
        grpc.StatusCode.FAILED_PRECONDITION,
        grpc.StatusCode.UNAVAILABLE,
    ],
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


def test_cancelled_after_deadline_surfaces_as_timeout():
    """A bounded wait must raise TimeoutError even if expiry arrives as CANCELLED.

    The sidecar can reset the stream (RST_STREAM CANCEL) just before gRPC raises
    DEADLINE_EXCEEDED locally, so the same expiry reaches the client under either
    code. Observed in CI against daprd from master; see
    test_orchestration_e2e_async.py::test_suspend_and_resume.
    """

    def cancel_after_budget_spent(*args, **kwargs):
        time.sleep(0.05)  # outlast the caller's budget, as a real expiry would
        raise _make_rpc_error(grpc.StatusCode.CANCELLED)

    c = TaskHubGrpcClient()
    c._stub = Mock()
    c._stub.WaitForInstanceCompletion.side_effect = cancel_after_budget_spent

    with pytest.raises(TimeoutError):
        c.wait_for_orchestration_completion('test-instance', timeout=0.01)


def test_cancelled_within_deadline_retries_then_succeeds(monkeypatch):
    """A server-sent CANCELLED with deadline budget remaining is retried."""
    instance_id = 'test-instance'

    from dapr.ext.workflow._durabletask.internal.protos import (
        ORCHESTRATION_STATUS_COMPLETED,
        GetInstanceResponse,
        WorkflowState,
    )

    response = GetInstanceResponse()
    response.exists = True
    state = WorkflowState()
    state.instanceId = instance_id
    state.workflowStatus = ORCHESTRATION_STATUS_COMPLETED
    response.workflowState.CopyFrom(state)

    sleeps = []
    monkeypatch.setattr(
        'dapr.ext.workflow._durabletask.client.time.sleep', lambda s: sleeps.append(s)
    )

    calls = {'n': 0}

    def fake_call(*args, **kwargs):
        calls['n'] += 1
        if calls['n'] == 1:
            raise _make_rpc_error(grpc.StatusCode.CANCELLED)
        return response

    c = TaskHubGrpcClient()
    c._stub = Mock()
    c._stub.WaitForInstanceCompletion.side_effect = fake_call

    res = c.wait_for_orchestration_completion(instance_id, timeout=300)
    assert res is not None
    assert res.runtime_status == OrchestrationStatus.COMPLETED
    assert calls['n'] == 2
    assert len(sleeps) == 1 and sleeps[0] > 0


def test_cancelled_unbounded_wait_retries_then_succeeds(monkeypatch):
    """With timeout=0 (unbounded), server-sent CANCELLED is retried with backoff."""
    instance_id = 'test-instance'

    from dapr.ext.workflow._durabletask.internal.protos import (
        ORCHESTRATION_STATUS_COMPLETED,
        GetInstanceResponse,
        WorkflowState,
    )

    response = GetInstanceResponse()
    response.exists = True
    state = WorkflowState()
    state.instanceId = instance_id
    state.workflowStatus = ORCHESTRATION_STATUS_COMPLETED
    response.workflowState.CopyFrom(state)

    sleeps = []
    monkeypatch.setattr(
        'dapr.ext.workflow._durabletask.client.time.sleep', lambda s: sleeps.append(s)
    )

    calls = {'n': 0}

    def fake_call(*args, **kwargs):
        calls['n'] += 1
        if calls['n'] == 1:
            raise _make_rpc_error(grpc.StatusCode.CANCELLED)
        return response

    c = TaskHubGrpcClient()
    c._stub = Mock()
    c._stub.WaitForInstanceCompletion.side_effect = fake_call

    res = c.wait_for_orchestration_completion(instance_id, timeout=0)
    assert res is not None
    assert res.runtime_status == OrchestrationStatus.COMPLETED
    assert calls['n'] == 2
    assert len(sleeps) == 1 and sleeps[0] > 0


def test_cancelled_unbounded_wait_persistent_gives_up_with_rpc_error(monkeypatch):
    """With timeout=0 (unbounded), persistent CANCELLED errors are retried only
    for the grace window, then the original RpcError propagates — NOT a hang and
    NOT a TimeoutError."""
    instance_id = 'test-instance'

    fake_time = [0.0]

    def fake_monotonic():
        fake_time[0] += 20.0
        return fake_time[0]

    monkeypatch.setattr('dapr.ext.workflow._durabletask.client.time.monotonic', fake_monotonic)
    monkeypatch.setattr('dapr.ext.workflow._durabletask.client.time.sleep', lambda s: None)

    c = TaskHubGrpcClient()
    c._stub = Mock()
    c._stub.WaitForInstanceCompletion.side_effect = _make_rpc_error(grpc.StatusCode.CANCELLED)

    with pytest.raises(grpc.RpcError) as exc_info:
        c.wait_for_orchestration_completion(instance_id, timeout=0)
    assert not isinstance(exc_info.value, TimeoutError)
    assert c._stub.WaitForInstanceCompletion.call_count >= 2


def test_unbounded_wait_retries_across_multiple_sidecar_restarts(monkeypatch):
    """An unbounded wait survives multiple sidecar restarts separated by long waits.

    Restarting the 30s transient window on each healthy re-issue prevents
    restarts separated by normal wait times from failing the orchestrator wait.
    """
    instance_id = 'test-instance'

    from dapr.ext.workflow._durabletask.internal.protos import (
        ORCHESTRATION_STATUS_COMPLETED,
        GetInstanceResponse,
        WorkflowState,
    )

    response = GetInstanceResponse()
    response.exists = True
    state = WorkflowState()
    state.instanceId = instance_id
    state.workflowStatus = ORCHESTRATION_STATUS_COMPLETED
    response.workflowState.CopyFrom(state)

    fake_time = [0.0]

    def fake_monotonic():
        return fake_time[0]

    monkeypatch.setattr('dapr.ext.workflow._durabletask.client.time.monotonic', fake_monotonic)
    monkeypatch.setattr('dapr.ext.workflow._durabletask.client.time.sleep', lambda s: None)

    calls = {'n': 0}

    def fake_call(*args, **kwargs):
        calls['n'] += 1
        if calls['n'] == 1:
            fake_time[0] += 10.0  # waited 10s before first restart
            raise _make_rpc_error(grpc.StatusCode.CANCELLED)
        if calls['n'] == 2:
            fake_time[0] += 60.0  # in-flight wait for 60s before second restart
            raise _make_rpc_error(grpc.StatusCode.CANCELLED)
        fake_time[0] += 5.0
        return response

    c = TaskHubGrpcClient()
    c._stub = Mock()
    c._stub.WaitForInstanceCompletion.side_effect = fake_call

    res = c.wait_for_orchestration_completion(instance_id, timeout=0)
    assert res is not None
    assert res.runtime_status == OrchestrationStatus.COMPLETED
    assert calls['n'] == 3


def test_unbounded_wait_caps_consecutive_in_flight_cancellations(monkeypatch):
    """When every wait attempt is CANCELLED after >= 1s, the client caps consecutive
    window resets (_MAX_CONSECUTIVE_TRANSIENT_RESETS) and eventually propagates
    the CANCELLED RpcError rather than looping forever."""
    instance_id = 'test-instance'

    fake_time = [0.0]

    def fake_monotonic():
        return fake_time[0]

    monkeypatch.setattr('dapr.ext.workflow._durabletask.client.time.monotonic', fake_monotonic)
    monkeypatch.setattr('dapr.ext.workflow._durabletask.client.time.sleep', lambda s: None)

    calls = {'n': 0}

    def fake_call(*args, **kwargs):
        calls['n'] += 1
        fake_time[0] += 5.0  # >= 1.0s in-flight before server cancellation
        raise _make_rpc_error(grpc.StatusCode.CANCELLED)

    c = TaskHubGrpcClient()
    c._stub = Mock()
    c._stub.WaitForInstanceCompletion.side_effect = fake_call

    with pytest.raises(grpc.RpcError) as exc_info:
        c.wait_for_orchestration_completion(instance_id, timeout=0)

    assert exc_info.value.code() == grpc.StatusCode.CANCELLED
    # Must have attempted beyond the max reset limit before exhausting the 30s window
    assert calls['n'] > TaskHubGrpcClient._MAX_CONSECUTIVE_TRANSIENT_RESETS


def test_client_close_sets_is_closed():
    """Closing the client marks is_closed as True."""
    c = TaskHubGrpcClient()
    c._channel = Mock()
    assert not c.is_closed
    c.close()
    assert c.is_closed


def test_cancelled_when_client_closed_reraises_immediately_without_retry(monkeypatch):
    """When the client is closed locally, CANCELLED is not retried and raises immediately."""
    instance_id = 'test-instance'
    sleeps = []
    monkeypatch.setattr(
        'dapr.ext.workflow._durabletask.client.time.sleep', lambda s: sleeps.append(s)
    )

    c = TaskHubGrpcClient()
    c._channel = Mock()
    c.close()
    c._stub = Mock()
    c._stub.WaitForInstanceCompletion.side_effect = _make_rpc_error(grpc.StatusCode.CANCELLED)

    with pytest.raises(grpc.RpcError):
        c.wait_for_orchestration_completion(instance_id, timeout=0)

    assert c._stub.WaitForInstanceCompletion.call_count == 1
    assert len(sleeps) == 0


def test_cancelled_with_channel_closed_details_reraises_immediately(monkeypatch):
    """When CANCELLED details indicate channel closure, it is raised immediately without retry."""
    instance_id = 'test-instance'
    sleeps = []
    monkeypatch.setattr(
        'dapr.ext.workflow._durabletask.client.time.sleep', lambda s: sleeps.append(s)
    )

    c = TaskHubGrpcClient()
    c._stub = Mock()
    c._stub.WaitForInstanceCompletion.side_effect = _make_rpc_error(
        grpc.StatusCode.CANCELLED, details='Channel closed!'
    )

    with pytest.raises(grpc.RpcError):
        c.wait_for_orchestration_completion(instance_id, timeout=0)

    assert c._stub.WaitForInstanceCompletion.call_count == 1
    assert len(sleeps) == 0


def test_in_flight_cancellation_on_client_close_repro(monkeypatch):
    """Repro from CasperGN: WaitForInstanceCompletion in flight is aborted when the client
    is closed locally. Must re-raise grpc.RpcError immediately without attempting to invoke
    a new RPC on the closed channel (which would raise ValueError: Cannot invoke RPC on closed channel!).
    """
    instance_id = 'test-instance'
    sleeps = []
    monkeypatch.setattr(
        'dapr.ext.workflow._durabletask.client.time.sleep', lambda s: sleeps.append(s)
    )

    c = TaskHubGrpcClient()
    c._channel = Mock()

    def fake_wait(*args, **kwargs):
        # Client is closed while wait is in-flight
        c.close()
        # gRPC raises CANCELLED on channel closure
        raise _make_rpc_error(grpc.StatusCode.CANCELLED, details='Channel closed!')

    c._stub = Mock()
    c._stub.WaitForInstanceCompletion.side_effect = fake_wait

    with pytest.raises(grpc.RpcError) as exc_info:
        c.wait_for_orchestration_completion(instance_id, timeout=0)

    # Must be grpc.RpcError, NOT ValueError("Cannot invoke RPC on closed channel!")
    assert isinstance(exc_info.value, grpc.RpcError)
    assert not isinstance(exc_info.value, ValueError)
    assert c._stub.WaitForInstanceCompletion.call_count == 1
    assert len(sleeps) == 0
