# -*- coding: utf-8 -*-

"""
Copyright 2026 The Dapr Authors
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

import unittest
from unittest import mock

from google.protobuf import timestamp_pb2, wrappers_pb2
from grpc import RpcError

import dapr.ext.workflow._durabletask.internal.protos as pb
from dapr.ext.workflow._durabletask.client import _new_rerun_request
from dapr.ext.workflow.aio.dapr_workflow_client import DaprWorkflowClient as AsyncWorkflowClient
from dapr.ext.workflow.dapr_workflow_client import DaprWorkflowClient
from dapr.ext.workflow.workflow_management import (
    _RERUNNABLE_EVENT_TYPES,
    UNSET,
    WorkflowHistoryEvent,
    WorkflowHistoryEventType,
    WorkflowInstanceIdPage,
)


class SimulatedRpcError(RpcError):
    def __init__(self, code, details):
        self._code = code
        self._details = details

    def code(self):
        return self._code

    def details(self):
        return self._details


def new_history_event(**kwargs) -> pb.HistoryEvent:
    kwargs.setdefault('timestamp', timestamp_pb2.Timestamp(seconds=1700000000))
    return pb.HistoryEvent(**kwargs)


class FakeTaskHubGrpcClient:
    """Stand-in for the engine client, recording what the public client asked for."""

    def __init__(self):
        self.pages = [pb.ListInstanceIDsResponse()]
        self.history = []
        self.rerun_result = 'rerun1'
        self.list_calls = []
        self.rerun_calls = []

    def list_instance_ids(self, *, page_size=None, continuation_token=None):
        self.list_calls.append((page_size, continuation_token))
        return self.pages[len(self.list_calls) - 1]

    def get_instance_history(self, instance_id: str):
        return self.history

    def rerun_orchestration_from_event(
        self,
        instance_id,
        event_id,
        *,
        new_instance_id=None,
        input=None,
        overwrite_input=False,
        new_child_instance_id=None,
    ):
        # Build the real request so the fake rejects what the engine would reject.
        _new_rerun_request(
            instance_id,
            event_id,
            new_instance_id=new_instance_id,
            input=input,
            overwrite_input=overwrite_input,
            new_child_instance_id=new_child_instance_id,
        )
        self.rerun_calls.append(
            {
                'instance_id': instance_id,
                'event_id': event_id,
                'new_instance_id': new_instance_id,
                'input': input,
                'overwrite_input': overwrite_input,
                'new_child_instance_id': new_child_instance_id,
            }
        )
        return self.rerun_result


class AsyncFakeTaskHubGrpcClient(FakeTaskHubGrpcClient):
    async def list_instance_ids(self, *, page_size=None, continuation_token=None):
        return super().list_instance_ids(page_size=page_size, continuation_token=continuation_token)

    async def get_instance_history(self, instance_id: str):
        return super().get_instance_history(instance_id)

    async def rerun_orchestration_from_event(self, instance_id, event_id, **kwargs):
        return super().rerun_orchestration_from_event(instance_id, event_id, **kwargs)


def new_client(fake: FakeTaskHubGrpcClient) -> DaprWorkflowClient:
    with mock.patch('dapr.ext.workflow._durabletask.client.TaskHubGrpcClient', return_value=fake):
        return DaprWorkflowClient()


def new_async_client(fake: AsyncFakeTaskHubGrpcClient) -> AsyncWorkflowClient:
    with mock.patch(
        'dapr.ext.workflow._durabletask.aio.client.AsyncTaskHubGrpcClient', return_value=fake
    ):
        return AsyncWorkflowClient()


class WorkflowHistoryEventTest(unittest.TestCase):
    def test_task_scheduled_carries_its_activity_name(self):
        event = new_history_event(
            eventId=7, taskScheduled=pb.TaskScheduledEvent(name='charge_card')
        )

        result = WorkflowHistoryEvent._from_proto(event)

        self.assertEqual(7, result.event_id)
        self.assertEqual(WorkflowHistoryEventType.TASK_SCHEDULED, result.event_type)
        self.assertEqual('charge_card', result.name)
        self.assertIsNone(result.task_scheduled_id)
        self.assertIsNone(result.failure_details)

    def test_completion_events_link_back_to_their_scheduling_event(self):
        event = new_history_event(eventId=8, taskCompleted=pb.TaskCompletedEvent(taskScheduledId=7))

        result = WorkflowHistoryEvent._from_proto(event)

        self.assertEqual(WorkflowHistoryEventType.TASK_COMPLETED, result.event_type)
        self.assertEqual(7, result.task_scheduled_id)
        self.assertIsNone(result.name)

    def test_failure_events_carry_the_error(self):
        failure_details = pb.TaskFailureDetails(
            errorMessage='boom',
            errorType='ValueError',
            stackTrace=wrappers_pb2.StringValue(value='line 1'),
        )
        event = new_history_event(
            eventId=9,
            taskFailed=pb.TaskFailedEvent(taskScheduledId=7, failureDetails=failure_details),
        )

        result = WorkflowHistoryEvent._from_proto(event)

        self.assertEqual('boom', result.failure_details.message)
        self.assertEqual('ValueError', result.failure_details.error_type)
        self.assertEqual('line 1', result.failure_details.stack_trace)

    def test_failure_without_a_stack_trace_reports_none(self):
        event = new_history_event(
            taskFailed=pb.TaskFailedEvent(
                failureDetails=pb.TaskFailureDetails(errorMessage='boom', errorType='ValueError')
            )
        )

        self.assertIsNone(WorkflowHistoryEvent._from_proto(event).failure_details.stack_trace)

    def test_a_workflow_failure_carries_the_error_too(self):
        event = new_history_event(
            executionCompleted=pb.ExecutionCompletedEvent(
                failureDetails=pb.TaskFailureDetails(errorMessage='boom', errorType='ValueError')
            )
        )

        result = WorkflowHistoryEvent._from_proto(event)

        self.assertEqual(WorkflowHistoryEventType.EXECUTION_COMPLETED, result.event_type)
        self.assertEqual('boom', result.failure_details.message)

    def test_a_successful_completion_has_no_error(self):
        event = new_history_event(
            executionCompleted=pb.ExecutionCompletedEvent(
                result=wrappers_pb2.StringValue(value='"done"')
            )
        )

        self.assertIsNone(WorkflowHistoryEvent._from_proto(event).failure_details)

    def test_an_event_type_without_a_name_reports_none(self):
        event = new_history_event(executionSuspended=pb.ExecutionSuspendedEvent())

        self.assertIsNone(WorkflowHistoryEvent._from_proto(event).name)

    def test_an_unset_payload_maps_to_unknown(self):
        result = WorkflowHistoryEvent._from_proto(new_history_event(eventId=1))

        self.assertEqual(WorkflowHistoryEventType.UNKNOWN, result.event_type)
        self.assertFalse(result.is_rerunnable)

    def test_an_unrecognised_event_type_maps_to_unknown_rather_than_raising(self):
        """A newer sidecar must not break history reads."""
        self.assertEqual(
            WorkflowHistoryEventType.UNKNOWN,
            WorkflowHistoryEventType('somethingTheRuntimeAddedLater'),
        )

    def test_every_event_type_the_proto_defines_is_mapped(self):
        oneof_fields = {
            field.name for field in pb.HistoryEvent.DESCRIPTOR.oneofs_by_name['eventType'].fields
        }
        mapped = {member.value for member in WorkflowHistoryEventType} - {
            WorkflowHistoryEventType.UNKNOWN.value
        }

        self.assertEqual(set(), oneof_fields - mapped)

    def test_only_the_three_restartable_event_types_are_rerunnable(self):
        rerunnable = {
            event_type
            for event_type in WorkflowHistoryEventType
            if WorkflowHistoryEvent(
                event_id=1,
                timestamp=None,
                event_type=event_type,
                name=None,
                task_scheduled_id=None,
                failure_details=None,
            ).is_rerunnable
        }

        self.assertEqual(_RERUNNABLE_EVENT_TYPES, rerunnable)
        self.assertEqual(
            {
                WorkflowHistoryEventType.TASK_SCHEDULED,
                WorkflowHistoryEventType.TIMER_CREATED,
                WorkflowHistoryEventType.CHILD_WORKFLOW_INSTANCE_CREATED,
            },
            rerunnable,
        )


class WorkflowInstanceIdPageTest(unittest.TestCase):
    def test_a_middle_page_carries_the_next_token(self):
        res = pb.ListInstanceIDsResponse(instanceIds=['a', 'b'], continuationToken='next')

        page = WorkflowInstanceIdPage._from_proto(res)

        self.assertEqual(['a', 'b'], page.instance_ids)
        self.assertEqual('next', page.continuation_token)

    def test_the_last_page_reports_no_token(self):
        page = WorkflowInstanceIdPage._from_proto(pb.ListInstanceIDsResponse(instanceIds=['a']))

        self.assertIsNone(page.continuation_token)

    def test_an_explicitly_empty_token_is_still_a_token(self):
        """HasField, not truthiness, decides: an empty token is set, not absent."""
        res = pb.ListInstanceIDsResponse(instanceIds=[], continuationToken='')

        self.assertEqual('', WorkflowInstanceIdPage._from_proto(res).continuation_token)


class ListWorkflowInstanceIdsTest(unittest.TestCase):
    def test_passes_pagination_arguments_through(self):
        fake = FakeTaskHubGrpcClient()
        client = new_client(fake)

        client.list_workflow_instance_ids(page_size=25, continuation_token='token1')

        self.assertEqual([(25, 'token1')], fake.list_calls)

    def test_defaults_to_no_pagination_arguments(self):
        fake = FakeTaskHubGrpcClient()
        client = new_client(fake)

        client.list_workflow_instance_ids()

        self.assertEqual([(None, None)], fake.list_calls)

    def test_returns_the_converted_page(self):
        fake = FakeTaskHubGrpcClient()
        fake.pages = [pb.ListInstanceIDsResponse(instanceIds=['a'], continuationToken='next')]
        client = new_client(fake)

        page = client.list_workflow_instance_ids()

        self.assertEqual(
            WorkflowInstanceIdPage(instance_ids=['a'], continuation_token='next'), page
        )


class ListingUnsupportedTest(unittest.TestCase):
    """The runtime returns bare errors for both listing misconfigurations, so they
    arrive as UNKNOWN with the message buried in the details."""

    def _client_raising(self, details):
        fake = FakeTaskHubGrpcClient()

        def boom(**kwargs):
            raise SimulatedRpcError(code='UNKNOWN', details=details)

        fake.list_instance_ids = boom
        return new_client(fake)

    def test_a_store_that_cannot_list_keys_gets_advice(self):
        client = self._client_raising('state store *inmemory.Store does not support listing keys')

        with self.assertRaises(NotImplementedError) as caught:
            client.list_workflow_instance_ids()

        self.assertIn('supports key listing', str(caught.exception))
        self.assertIsInstance(caught.exception.__cause__, SimulatedRpcError)

    def test_a_missing_actor_store_gets_advice(self):
        client = self._client_raising('no state store with actor support found')

        with self.assertRaises(NotImplementedError) as caught:
            client.list_workflow_instance_ids()

        self.assertIn('actorStateStore', str(caught.exception))

    def test_an_unrelated_rpc_error_is_left_alone(self):
        client = self._client_raising('connection refused')

        with self.assertRaises(SimulatedRpcError):
            client.list_workflow_instance_ids()

    def test_the_iterator_surfaces_the_same_advice(self):
        client = self._client_raising('state store *inmemory.Store does not support listing keys')

        with self.assertRaises(NotImplementedError):
            list(client.iter_workflow_instance_ids())


class IterWorkflowInstanceIdsTest(unittest.TestCase):
    def test_follows_the_continuation_token_across_pages(self):
        fake = FakeTaskHubGrpcClient()
        fake.pages = [
            pb.ListInstanceIDsResponse(instanceIds=['a', 'b'], continuationToken='page2'),
            pb.ListInstanceIDsResponse(instanceIds=['c'], continuationToken='page3'),
            pb.ListInstanceIDsResponse(instanceIds=['d']),
        ]
        client = new_client(fake)

        self.assertEqual(['a', 'b', 'c', 'd'], list(client.iter_workflow_instance_ids()))
        self.assertEqual(
            [(1024, None), (1024, 'page2'), (1024, 'page3')],
            fake.list_calls,
        )

    def test_stops_on_the_first_page_when_there_is_no_token(self):
        fake = FakeTaskHubGrpcClient()
        fake.pages = [pb.ListInstanceIDsResponse(instanceIds=['a'])]
        client = new_client(fake)

        self.assertEqual(['a'], list(client.iter_workflow_instance_ids()))
        self.assertEqual(1, len(fake.list_calls))

    def test_yields_nothing_when_the_app_has_no_instances(self):
        fake = FakeTaskHubGrpcClient()
        client = new_client(fake)

        self.assertEqual([], list(client.iter_workflow_instance_ids()))

    def test_keeps_paging_through_an_empty_page_that_carries_a_token(self):
        fake = FakeTaskHubGrpcClient()
        fake.pages = [
            pb.ListInstanceIDsResponse(instanceIds=[], continuationToken='page2'),
            pb.ListInstanceIDsResponse(instanceIds=['a']),
        ]
        client = new_client(fake)

        self.assertEqual(['a'], list(client.iter_workflow_instance_ids()))

    def test_stops_on_an_empty_token_instead_of_looping_forever(self):
        """An empty token is not a usable cursor: stores that emit one read it as
        "first page", so following it would re-yield page 1 indefinitely."""
        fake = FakeTaskHubGrpcClient()
        fake.pages = [pb.ListInstanceIDsResponse(instanceIds=['a'], continuationToken='')]
        client = new_client(fake)

        self.assertEqual(['a'], list(client.iter_workflow_instance_ids()))
        self.assertEqual(1, len(fake.list_calls))

    def test_fetches_lazily(self):
        fake = FakeTaskHubGrpcClient()
        fake.pages = [
            pb.ListInstanceIDsResponse(instanceIds=['a'], continuationToken='page2'),
            pb.ListInstanceIDsResponse(instanceIds=['b']),
        ]
        client = new_client(fake)

        instances = client.iter_workflow_instance_ids()
        next(instances)

        self.assertEqual(1, len(fake.list_calls))

    def test_honours_the_page_size(self):
        fake = FakeTaskHubGrpcClient()
        client = new_client(fake)

        list(client.iter_workflow_instance_ids(page_size=10))

        self.assertEqual([(10, None)], fake.list_calls)


class GetWorkflowHistoryTest(unittest.TestCase):
    def test_converts_every_event(self):
        fake = FakeTaskHubGrpcClient()
        fake.history = [
            new_history_event(eventId=1, executionStarted=pb.ExecutionStartedEvent(name='order')),
            new_history_event(eventId=2, taskScheduled=pb.TaskScheduledEvent(name='charge')),
        ]
        client = new_client(fake)

        history = client.get_workflow_history('instance1')

        self.assertEqual(
            [
                (1, WorkflowHistoryEventType.EXECUTION_STARTED, 'order'),
                (2, WorkflowHistoryEventType.TASK_SCHEDULED, 'charge'),
            ],
            [(e.event_id, e.event_type, e.name) for e in history],
        )

    def test_an_empty_history_is_an_empty_list(self):
        client = new_client(FakeTaskHubGrpcClient())

        self.assertEqual([], client.get_workflow_history('instance1'))


class RerunWorkflowFromEventTest(unittest.TestCase):
    def test_returns_the_new_instance_id(self):
        fake = FakeTaskHubGrpcClient()
        client = new_client(fake)

        self.assertEqual('rerun1', client.rerun_workflow_from_event('instance1', 4))

    def test_omitting_input_does_not_ask_the_engine_to_overwrite(self):
        """Otherwise the runtime would clear an input the caller never mentioned."""
        fake = FakeTaskHubGrpcClient()
        client = new_client(fake)

        client.rerun_workflow_from_event('instance1', 4)

        self.assertFalse(fake.rerun_calls[0]['overwrite_input'])

    def test_passing_the_sentinel_explicitly_matches_omitting_it(self):
        """Forwarding code needs UNSET to mean exactly "not supplied"."""
        fake = FakeTaskHubGrpcClient()
        client = new_client(fake)

        client.rerun_workflow_from_event('instance1', 4, input=UNSET)

        self.assertFalse(fake.rerun_calls[0]['overwrite_input'])

    def test_the_sentinel_is_exported_for_forwarding_code(self):
        import dapr.ext.workflow as wf

        self.assertIs(UNSET, wf.UNSET)
        self.assertEqual('<unset>', repr(wf.UNSET))

    def test_an_explicit_none_input_asks_the_engine_to_overwrite(self):
        """None is a value, not an omission: it clears the input."""
        fake = FakeTaskHubGrpcClient()
        client = new_client(fake)

        client.rerun_workflow_from_event('instance1', 4, input=None)

        self.assertIsNone(fake.rerun_calls[0]['input'])
        self.assertTrue(fake.rerun_calls[0]['overwrite_input'])

    def test_rejects_a_negative_event_id(self):
        """WorkflowHistoryEvent.event_id is -1 for events the runtime gives no ID,
        so passing one straight back is a reachable mistake."""
        fake = FakeTaskHubGrpcClient()
        client = new_client(fake)

        with self.assertRaises(ValueError) as caught:
            client.rerun_workflow_from_event('instance1', -1)

        self.assertIn('event_id must be between 0 and', str(caught.exception))
        self.assertEqual([], fake.rerun_calls)

    def test_forwards_every_argument(self):
        fake = FakeTaskHubGrpcClient()
        client = new_client(fake)

        client.rerun_workflow_from_event(
            'instance1',
            4,
            new_instance_id='new1',
            input={'amount': 10},
            new_child_workflow_instance_id='child1',
        )

        self.assertEqual(
            {
                'instance_id': 'instance1',
                'event_id': 4,
                'new_instance_id': 'new1',
                'input': {'amount': 10},
                'overwrite_input': True,
                'new_child_instance_id': 'child1',
            },
            fake.rerun_calls[0],
        )


class AsyncWorkflowManagementTest(unittest.IsolatedAsyncioTestCase):
    async def test_list_returns_the_converted_page(self):
        fake = AsyncFakeTaskHubGrpcClient()
        fake.pages = [pb.ListInstanceIDsResponse(instanceIds=['a'], continuationToken='next')]
        client = new_async_client(fake)

        page = await client.list_workflow_instance_ids(page_size=25)

        self.assertEqual(
            WorkflowInstanceIdPage(instance_ids=['a'], continuation_token='next'), page
        )
        self.assertEqual([(25, None)], fake.list_calls)

    async def test_iter_follows_the_continuation_token_across_pages(self):
        fake = AsyncFakeTaskHubGrpcClient()
        fake.pages = [
            pb.ListInstanceIDsResponse(instanceIds=['a'], continuationToken='page2'),
            pb.ListInstanceIDsResponse(instanceIds=['b']),
        ]
        client = new_async_client(fake)

        self.assertEqual(
            ['a', 'b'], [instance_id async for instance_id in client.iter_workflow_instance_ids()]
        )
        self.assertEqual([(1024, None), (1024, 'page2')], fake.list_calls)

    async def test_iter_stops_on_an_empty_token_instead_of_looping_forever(self):
        fake = AsyncFakeTaskHubGrpcClient()
        fake.pages = [pb.ListInstanceIDsResponse(instanceIds=['a'], continuationToken='')]
        client = new_async_client(fake)

        collected = [instance_id async for instance_id in client.iter_workflow_instance_ids()]

        self.assertEqual(['a'], collected)
        self.assertEqual(1, len(fake.list_calls))

    async def test_iter_fetches_lazily(self):
        """An async generator body does not start until the first __anext__, so
        laziness here is a different mechanism from the sync generator's."""
        fake = AsyncFakeTaskHubGrpcClient()
        fake.pages = [
            pb.ListInstanceIDsResponse(instanceIds=['a'], continuationToken='page2'),
            pb.ListInstanceIDsResponse(instanceIds=['b']),
        ]
        client = new_async_client(fake)

        instances = client.iter_workflow_instance_ids()
        self.assertEqual([], fake.list_calls)

        self.assertEqual('a', await anext(instances))
        self.assertEqual(1, len(fake.list_calls))

    async def test_get_history_converts_every_event(self):
        fake = AsyncFakeTaskHubGrpcClient()
        fake.history = [new_history_event(eventId=2, taskScheduled=pb.TaskScheduledEvent(name='c'))]
        client = new_async_client(fake)

        history = await client.get_workflow_history('instance1')

        self.assertEqual([(2, 'c')], [(e.event_id, e.name) for e in history])

    async def test_rerun_omitting_input_does_not_ask_the_engine_to_overwrite(self):
        fake = AsyncFakeTaskHubGrpcClient()
        client = new_async_client(fake)

        result = await client.rerun_workflow_from_event('instance1', 4)

        self.assertEqual('rerun1', result)
        self.assertFalse(fake.rerun_calls[0]['overwrite_input'])

    async def test_rerun_forwards_every_argument(self):
        fake = AsyncFakeTaskHubGrpcClient()
        client = new_async_client(fake)

        await client.rerun_workflow_from_event(
            'instance1',
            4,
            new_instance_id='new1',
            input=None,
            new_child_workflow_instance_id='child1',
        )

        self.assertEqual(
            {
                'instance_id': 'instance1',
                'event_id': 4,
                'new_instance_id': 'new1',
                'input': None,
                'overwrite_input': True,
                'new_child_instance_id': 'child1',
            },
            fake.rerun_calls[0],
        )


if __name__ == '__main__':
    unittest.main()
