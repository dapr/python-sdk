from unittest.mock import Mock

import pytest

from durabletask.client import TaskHubGrpcClient


@pytest.mark.parametrize("timeout", [None, 0, 5])
def test_wait_for_orchestration_start_timeout(timeout):
    instance_id = "test-instance"

    from durabletask.internal.orchestrator_service_pb2 import (
        ORCHESTRATION_STATUS_RUNNING,
        GetInstanceResponse,
        OrchestrationState,
    )

    response = GetInstanceResponse()
    state = OrchestrationState()
    state.instanceId = instance_id
    state.orchestrationStatus = ORCHESTRATION_STATUS_RUNNING
    response.orchestrationState.CopyFrom(state)

    c = TaskHubGrpcClient()
    c._stub = Mock()
    c._stub.WaitForInstanceStart.return_value = response

    grpc_timeout = None if timeout is None else timeout
    c.wait_for_orchestration_start(instance_id, timeout=grpc_timeout)

    # Verify WaitForInstanceStart was called with timeout=None
    c._stub.WaitForInstanceStart.assert_called_once()
    _, kwargs = c._stub.WaitForInstanceStart.call_args
    if timeout is None or timeout == 0:
        assert kwargs.get("timeout") is None
    else:
        assert kwargs.get("timeout") == timeout


@pytest.mark.parametrize("timeout", [None, 0, 5])
def test_wait_for_orchestration_completion_timeout(timeout):
    instance_id = "test-instance"

    from durabletask.internal.orchestrator_service_pb2 import (
        ORCHESTRATION_STATUS_COMPLETED,
        GetInstanceResponse,
        OrchestrationState,
    )

    response = GetInstanceResponse()
    state = OrchestrationState()
    state.instanceId = instance_id
    state.orchestrationStatus = ORCHESTRATION_STATUS_COMPLETED
    response.orchestrationState.CopyFrom(state)

    c = TaskHubGrpcClient()
    c._stub = Mock()
    c._stub.WaitForInstanceCompletion.return_value = response

    grpc_timeout = None if timeout is None else timeout
    c.wait_for_orchestration_completion(instance_id, timeout=grpc_timeout)

    # Verify WaitForInstanceStart was called with timeout=None
    c._stub.WaitForInstanceCompletion.assert_called_once()
    _, kwargs = c._stub.WaitForInstanceCompletion.call_args
    if timeout is None or timeout == 0:
        assert kwargs.get("timeout") is None
    else:
        assert kwargs.get("timeout") == timeout
