# -*- coding: utf-8 -*-
# Copyright 2026 The Dapr Authors
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#     http://www.apache.org/licenses/LICENSE-2.0
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Engine-client coverage for the workflow management RPCs (list, history, rerun)."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from google.protobuf import timestamp_pb2, wrappers_pb2

import dapr.ext.workflow._durabletask.internal.protos as pb
from dapr.ext.workflow._durabletask.aio.client import AsyncTaskHubGrpcClient
from dapr.ext.workflow._durabletask.client import TaskHubGrpcClient


def _sync_client() -> TaskHubGrpcClient:
    with patch('dapr.ext.workflow._durabletask.internal.shared.get_grpc_channel'):
        client = TaskHubGrpcClient()
    client._stub = MagicMock()
    return client


def _async_client() -> AsyncTaskHubGrpcClient:
    with patch('dapr.ext.workflow._durabletask.aio.internal.shared.get_grpc_aio_channel'):
        client = AsyncTaskHubGrpcClient()
    stub = MagicMock()
    client._get_stub = lambda: stub
    return client


def test_list_instance_ids_omits_unset_pagination_fields():
    client = _sync_client()
    client._stub.ListInstanceIDs.return_value = pb.ListInstanceIDsResponse()

    client.list_instance_ids()

    req = client._stub.ListInstanceIDs.call_args[0][0]
    assert not req.HasField('pageSize')
    assert not req.HasField('continuationToken')


def test_list_instance_ids_forwards_pagination_fields():
    client = _sync_client()
    client._stub.ListInstanceIDs.return_value = pb.ListInstanceIDsResponse()

    client.list_instance_ids(page_size=50, continuation_token='token1')

    req = client._stub.ListInstanceIDs.call_args[0][0]
    assert req.pageSize == 50
    assert req.continuationToken == 'token1'


def test_list_instance_ids_returns_the_raw_response():
    client = _sync_client()
    expected = pb.ListInstanceIDsResponse(instanceIds=['a', 'b'], continuationToken='next')
    client._stub.ListInstanceIDs.return_value = expected

    assert client.list_instance_ids() is expected


def test_get_instance_history_unwraps_events():
    client = _sync_client()
    events = [pb.HistoryEvent(eventId=1), pb.HistoryEvent(eventId=2)]
    client._stub.GetInstanceHistory.return_value = pb.GetInstanceHistoryResponse(events=events)

    result = client.get_instance_history('instance1')

    assert [e.eventId for e in result] == [1, 2]
    assert client._stub.GetInstanceHistory.call_args[0][0].instanceId == 'instance1'


def test_get_instance_history_of_an_empty_history():
    client = _sync_client()
    client._stub.GetInstanceHistory.return_value = pb.GetInstanceHistoryResponse()

    assert client.get_instance_history('instance1') == []


def test_rerun_returns_the_new_instance_id():
    client = _sync_client()
    client._stub.RerunWorkflowFromEvent.return_value = pb.RerunWorkflowFromEventResponse(
        newInstanceID='rerun1'
    )

    assert client.rerun_orchestration_from_event('instance1', 4) == 'rerun1'


def test_rerun_sends_source_instance_and_event_id():
    client = _sync_client()
    client._stub.RerunWorkflowFromEvent.return_value = pb.RerunWorkflowFromEventResponse()

    client.rerun_orchestration_from_event('instance1', 4)

    req = client._stub.RerunWorkflowFromEvent.call_args[0][0]
    assert req.sourceInstanceID == 'instance1'
    assert req.eventID == 4


def test_rerun_without_overwrite_leaves_the_original_input_alone():
    """overwriteInput must stay false, or the runtime nulls the input."""
    client = _sync_client()
    client._stub.RerunWorkflowFromEvent.return_value = pb.RerunWorkflowFromEventResponse()

    client.rerun_orchestration_from_event('instance1', 4)

    req = client._stub.RerunWorkflowFromEvent.call_args[0][0]
    assert req.overwriteInput is False
    assert not req.HasField('input')


def test_rerun_with_overwrite_and_no_input_clears_the_input():
    """The flag without a value is how the wire says "set the input to null"."""
    client = _sync_client()
    client._stub.RerunWorkflowFromEvent.return_value = pb.RerunWorkflowFromEventResponse()

    client.rerun_orchestration_from_event('instance1', 4, input=None, overwrite_input=True)

    req = client._stub.RerunWorkflowFromEvent.call_args[0][0]
    assert req.overwriteInput is True
    assert not req.HasField('input')


def test_rerun_with_an_input_serializes_it_to_json():
    client = _sync_client()
    client._stub.RerunWorkflowFromEvent.return_value = pb.RerunWorkflowFromEventResponse()

    client.rerun_orchestration_from_event(
        'instance1', 4, input={'amount': 10}, overwrite_input=True
    )

    req = client._stub.RerunWorkflowFromEvent.call_args[0][0]
    assert req.overwriteInput is True
    assert req.input == wrappers_pb2.StringValue(value='{"amount": 10}')


def test_rerun_with_a_falsy_input_still_overwrites():
    """A falsy payload must not be mistaken for an omitted one."""
    client = _sync_client()
    client._stub.RerunWorkflowFromEvent.return_value = pb.RerunWorkflowFromEventResponse()

    client.rerun_orchestration_from_event('instance1', 4, input=0, overwrite_input=True)

    req = client._stub.RerunWorkflowFromEvent.call_args[0][0]
    assert req.overwriteInput is True
    assert req.input == wrappers_pb2.StringValue(value='0')


def test_rerun_rejects_a_negative_event_id_before_calling_the_stub():
    """eventID is uint32 on the wire, so protobuf would reject -1 with a message
    naming neither the argument nor the reason. -1 is reachable: it is what the
    runtime reports for history events it assigns no ID to."""
    client = _sync_client()

    with pytest.raises(ValueError, match='event_id must be non-negative, got -1'):
        client.rerun_orchestration_from_event('instance1', -1)

    client._stub.RerunWorkflowFromEvent.assert_not_called()


def test_rerun_accepts_event_id_zero():
    """Zero is a valid event id, so the guard must not key off falsiness."""
    client = _sync_client()
    client._stub.RerunWorkflowFromEvent.return_value = pb.RerunWorkflowFromEventResponse()

    client.rerun_orchestration_from_event('instance1', 0)

    assert client._stub.RerunWorkflowFromEvent.call_args[0][0].eventID == 0


def test_rerun_omits_unset_instance_ids():
    client = _sync_client()
    client._stub.RerunWorkflowFromEvent.return_value = pb.RerunWorkflowFromEventResponse()

    client.rerun_orchestration_from_event('instance1', 4)

    req = client._stub.RerunWorkflowFromEvent.call_args[0][0]
    assert not req.HasField('newInstanceID')
    assert not req.HasField('newChildWorkflowInstanceID')


def test_rerun_forwards_both_new_instance_ids():
    client = _sync_client()
    client._stub.RerunWorkflowFromEvent.return_value = pb.RerunWorkflowFromEventResponse()

    client.rerun_orchestration_from_event(
        'instance1', 4, new_instance_id='new1', new_child_instance_id='child1'
    )

    req = client._stub.RerunWorkflowFromEvent.call_args[0][0]
    assert req.newInstanceID == 'new1'
    assert req.newChildWorkflowInstanceID == 'child1'


def test_history_timestamps_survive_the_round_trip():
    client = _sync_client()
    event = pb.HistoryEvent(
        eventId=1,
        timestamp=timestamp_pb2.Timestamp(seconds=1700000000),
        taskScheduled=pb.TaskScheduledEvent(name='charge'),
    )
    client._stub.GetInstanceHistory.return_value = pb.GetInstanceHistoryResponse(events=[event])

    assert client.get_instance_history('instance1')[0].timestamp.seconds == 1700000000


@pytest.mark.asyncio
async def test_async_list_instance_ids_forwards_pagination_fields():
    client = _async_client()
    client._get_stub().ListInstanceIDs = AsyncMock(return_value=pb.ListInstanceIDsResponse())

    await client.list_instance_ids(page_size=50, continuation_token='token1')

    req = client._get_stub().ListInstanceIDs.call_args[0][0]
    assert req.pageSize == 50
    assert req.continuationToken == 'token1'


@pytest.mark.asyncio
async def test_async_get_instance_history_unwraps_events():
    client = _async_client()
    client._get_stub().GetInstanceHistory = AsyncMock(
        return_value=pb.GetInstanceHistoryResponse(events=[pb.HistoryEvent(eventId=3)])
    )

    result = await client.get_instance_history('instance1')

    assert [e.eventId for e in result] == [3]


@pytest.mark.asyncio
async def test_async_rerun_builds_the_same_request_as_the_sync_client():
    client = _async_client()
    client._get_stub().RerunWorkflowFromEvent = AsyncMock(
        return_value=pb.RerunWorkflowFromEventResponse(newInstanceID='rerun1')
    )

    omitted = await client.rerun_orchestration_from_event('instance1', 4)
    req_omitted = client._get_stub().RerunWorkflowFromEvent.call_args[0][0]

    await client.rerun_orchestration_from_event('instance1', 4, input=None, overwrite_input=True)
    req_none = client._get_stub().RerunWorkflowFromEvent.call_args[0][0]

    assert omitted == 'rerun1'
    assert req_omitted.overwriteInput is False
    assert req_none.overwriteInput is True
