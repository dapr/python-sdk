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
from datetime import datetime
from unittest import mock

from google.protobuf import timestamp_pb2, wrappers_pb2
from grpc import RpcError, StatusCode

import dapr.ext.workflow._durabletask.internal.orchestrator_service_pb2_grpc as stubs
import dapr.ext.workflow._durabletask.internal.protos as pb
from dapr.ext.workflow import (
    WorkflowSchedule,
    WorkflowSchedulePage,
    WorkflowScheduleRun,
    WorkflowScheduleState,
    WorkflowScheduleStatus,
    WorkflowStatus,
    alternate_name,
)
from dapr.ext.workflow.aio.dapr_workflow_client import DaprWorkflowClient as AsyncWorkflowClient
from dapr.ext.workflow.dapr_workflow_client import DaprWorkflowClient

CREATED_AT = datetime(2026, 10, 29, 9, 0, 0)
LAST_RUN_AT = datetime(2026, 10, 29, 9, 30, 0)
NEXT_RUN_AT = datetime(2026, 10, 29, 10, 0, 0)


class SimulatedRpcError(RpcError):
    def __init__(self, code, details):
        self._code = code
        self._details = details

    def code(self):
        return self._code

    def details(self):
        return self._details


def timestamp_of(dt: datetime) -> timestamp_pb2.Timestamp:
    ts = timestamp_pb2.Timestamp()
    ts.FromDatetime(dt)
    return ts


def new_schedule_proto() -> pb.WorkflowSchedule:
    """A schedule as the runtime returns it from Get, with every field set."""
    last_run = pb.WorkflowScheduleRun(
        instanceId='nightly_20261029T093000Z',
        runtimeStatus=pb.ORCHESTRATION_STATUS_COMPLETED,
        createdTimestamp=timestamp_of(LAST_RUN_AT),
        lastUpdatedTimestamp=timestamp_of(LAST_RUN_AT),
        output=wrappers_pb2.StringValue(value='"done"'),
    )
    status = pb.WorkflowScheduleStatus(
        state=pb.WORKFLOW_SCHEDULE_STATE_ACTIVE,
        createdAt=timestamp_of(CREATED_AT),
        nextRunTime=timestamp_of(NEXT_RUN_AT),
        lastRunTime=timestamp_of(LAST_RUN_AT),
        runCount=3,
        lastRun=last_run,
    )
    return pb.WorkflowSchedule(
        name='nightly',
        workflowName='report',
        schedule='0 30 9 * * *',
        input=wrappers_pb2.StringValue(value='{"region": "eu"}'),
        dueTime=timestamp_of(CREATED_AT),
        repeats=10,
        targetAppID='reports',
        status=status,
    )


def report_workflow(ctx, region):
    pass


class WorkflowScheduleConversionTest(unittest.TestCase):
    def test_a_schedule_and_its_status_convert_to_sdk_types(self):
        expected_run = WorkflowScheduleRun(
            instance_id='nightly_20261029T093000Z',
            runtime_status=WorkflowStatus.COMPLETED,
            created_at=LAST_RUN_AT,
            last_updated_at=LAST_RUN_AT,
            serialized_output='"done"',
            failure_details=None,
        )
        expected_status = WorkflowScheduleStatus(
            state=WorkflowScheduleState.ACTIVE,
            created_at=CREATED_AT,
            next_run_time=NEXT_RUN_AT,
            last_run_time=LAST_RUN_AT,
            run_count=3,
            last_run=expected_run,
            failure_message=None,
        )
        expected = WorkflowSchedule(
            name='nightly',
            workflow_name='report',
            schedule='0 30 9 * * *',
            serialized_input='{"region": "eu"}',
            due_time=CREATED_AT,
            expiration_time=None,
            repeats=10,
            app_id='reports',
            app_namespace=None,
            skip_missed=False,
            status=expected_status,
        )

        self.assertEqual(expected, WorkflowSchedule._from_proto(new_schedule_proto()))

    def test_a_schedule_before_its_first_run_has_no_run_fields(self):
        schedule_proto = pb.WorkflowSchedule(
            name='nightly',
            workflowName='report',
            schedule='@daily',
            status=pb.WorkflowScheduleStatus(createdAt=timestamp_of(CREATED_AT)),
        )

        schedule = WorkflowSchedule._from_proto(schedule_proto)

        self.assertIsNone(schedule.serialized_input)
        self.assertIsNone(schedule.repeats)
        self.assertIsNone(schedule.app_id)
        self.assertFalse(schedule.skip_missed)
        self.assertIsNone(schedule.status.last_run)
        self.assertIsNone(schedule.status.last_run_time)
        self.assertEqual(0, schedule.status.run_count)

    def test_a_failed_schedule_carries_its_failure_message(self):
        status_proto = pb.WorkflowScheduleStatus(
            state=pb.WORKFLOW_SCHEDULE_STATE_FAILED,
            failureMessage=wrappers_pb2.StringValue(value='boom'),
        )

        status = WorkflowScheduleStatus._from_proto(status_proto)

        self.assertEqual(WorkflowScheduleState.FAILED, status.state)
        self.assertEqual('boom', status.failure_message)
        self.assertIsNone(status.next_run_time)

    def test_a_run_that_cannot_be_read_has_only_its_instance_id(self):
        run = WorkflowScheduleRun._from_proto(pb.WorkflowScheduleRun(instanceId='nightly_x'))

        self.assertEqual(
            WorkflowScheduleRun('nightly_x', None, None, None, None, None),
            run,
        )

    def test_a_failed_run_carries_the_error(self):
        run_proto = pb.WorkflowScheduleRun(
            instanceId='nightly_x',
            runtimeStatus=pb.ORCHESTRATION_STATUS_FAILED,
            failureDetails=pb.TaskFailureDetails(errorMessage='boom', errorType='ValueError'),
        )

        run = WorkflowScheduleRun._from_proto(run_proto)

        self.assertEqual(WorkflowStatus.FAILED, run.runtime_status)
        self.assertEqual('boom', run.failure_details.message)
        self.assertEqual('ValueError', run.failure_details.error_type)

    def test_states_and_statuses_the_sdk_does_not_know_map_to_unknown(self):
        """A newer sidecar must not break schedule reads."""
        self.assertEqual(WorkflowScheduleState.UNKNOWN, WorkflowScheduleState(42))
        run = WorkflowScheduleRun._from_proto(
            pb.WorkflowScheduleRun(instanceId='x', runtimeStatus=42)
        )
        self.assertEqual(WorkflowStatus.UNKNOWN, run.runtime_status)

    def test_an_empty_continuation_token_means_the_last_page(self):
        """Sending '' back would fetch the first page again."""
        page = WorkflowSchedulePage._from_proto(
            pb.ListWorkflowSchedulesResponse(continuationToken='')
        )

        self.assertIsNone(page.continuation_token)

    def test_every_state_the_proto_defines_is_mapped(self):
        mapped = {state.value for state in WorkflowScheduleState}

        self.assertLessEqual(set(pb.WorkflowScheduleState.values()), mapped)


class WorkflowScheduleClientTest(unittest.TestCase):
    """Drives the public client against a mocked TaskHubSidecarService stub."""

    def setUp(self):
        self.stub = mock.MagicMock()
        stub_patch = mock.patch.object(stubs, 'TaskHubSidecarServiceStub', return_value=self.stub)
        channel_patch = mock.patch(
            'dapr.ext.workflow._durabletask.internal.shared.get_grpc_channel'
        )
        for patcher in (stub_patch, channel_patch):
            patcher.start()
            self.addCleanup(patcher.stop)
        self.client = DaprWorkflowClient()

    def sent(self, method: str):
        return getattr(self.stub, method).call_args[0][0]

    def test_create_sends_every_option(self):
        self.client.create_workflow_schedule(
            'nightly',
            report_workflow,
            '0 30 9 * * *',
            input={'region': 'eu'},
            due_time=CREATED_AT,
            expiration_time=NEXT_RUN_AT,
            repeats=10,
            app_id='reports',
            app_namespace='prod',
            overwrite=True,
        )

        req = self.sent('CreateWorkflowSchedule')
        self.assertTrue(req.overwrite)
        self.assertEqual('nightly', req.schedule.name)
        self.assertEqual('report_workflow', req.schedule.workflowName)
        self.assertEqual('0 30 9 * * *', req.schedule.schedule)
        self.assertEqual('{"region": "eu"}', req.schedule.input.value)
        self.assertEqual(CREATED_AT, req.schedule.dueTime.ToDatetime())
        self.assertEqual(NEXT_RUN_AT, req.schedule.expirationTime.ToDatetime())
        self.assertEqual(10, req.schedule.repeats)
        self.assertEqual('reports', req.schedule.targetAppID)
        self.assertEqual('prod', req.schedule.targetAppNamespace)

    def test_create_leaves_unset_options_off_the_wire(self):
        self.client.create_workflow_schedule('nightly', 'report', '@daily')

        req = self.sent('CreateWorkflowSchedule')
        self.assertFalse(req.overwrite)
        for field in (
            'input',
            'dueTime',
            'expirationTime',
            'repeats',
            'targetAppID',
            'targetAppNamespace',
            'skipMissed',
            'status',
        ):
            self.assertFalse(req.schedule.HasField(field), field)

    def test_skip_missed_reaches_the_request_and_is_read_back(self):
        self.client.create_workflow_schedule('nightly', 'report', '@daily', skip_missed=True)
        sent_schedule = self.sent('CreateWorkflowSchedule').schedule
        self.stub.GetWorkflowSchedule.return_value = pb.GetWorkflowScheduleResponse(
            schedule=sent_schedule
        )

        schedule = self.client.get_workflow_schedule('nightly')

        self.assertTrue(sent_schedule.HasField('skipMissed'))
        self.assertTrue(sent_schedule.skipMissed)
        self.assertTrue(schedule.skip_missed)

    def test_create_keeps_a_falsy_input(self):
        self.client.create_workflow_schedule('nightly', 'report', '@daily', input=0)

        self.assertEqual('0', self.sent('CreateWorkflowSchedule').schedule.input.value)

    def test_create_uses_a_workflow_alternate_name(self):
        @alternate_name('renamed_report')
        def renamed(ctx, _):
            pass

        self.client.create_workflow_schedule('nightly', renamed, '@daily')

        self.assertEqual(
            'renamed_report', self.sent('CreateWorkflowSchedule').schedule.workflowName
        )

    def test_get_returns_the_converted_schedule(self):
        response = pb.GetWorkflowScheduleResponse(schedule=new_schedule_proto())
        self.stub.GetWorkflowSchedule.return_value = response

        schedule = self.client.get_workflow_schedule('nightly')

        self.assertEqual('nightly', self.sent('GetWorkflowSchedule').name)
        self.assertEqual(WorkflowSchedule._from_proto(new_schedule_proto()), schedule)

    def test_get_of_a_missing_schedule_raises_not_found(self):
        self.stub.GetWorkflowSchedule.side_effect = SimulatedRpcError(
            StatusCode.NOT_FOUND, 'workflow schedule "nightly" not found'
        )

        with self.assertRaises(RpcError) as caught:
            self.client.get_workflow_schedule('nightly')

        self.assertEqual(StatusCode.NOT_FOUND, caught.exception.code())

    def test_list_passes_pagination_through_and_converts_the_page(self):
        self.stub.ListWorkflowSchedules.return_value = pb.ListWorkflowSchedulesResponse(
            schedules=[new_schedule_proto()], continuationToken='next'
        )

        page = self.client.list_workflow_schedules(page_size=5, continuation_token='token1')

        req = self.sent('ListWorkflowSchedules')
        self.assertEqual(5, req.pageSize)
        self.assertEqual('token1', req.continuationToken)
        expected = WorkflowSchedulePage(
            schedules=[WorkflowSchedule._from_proto(new_schedule_proto())],
            continuation_token='next',
        )
        self.assertEqual(expected, page)

    def test_list_defaults_to_no_pagination_and_reports_the_last_page(self):
        self.stub.ListWorkflowSchedules.return_value = pb.ListWorkflowSchedulesResponse()

        page = self.client.list_workflow_schedules()

        req = self.sent('ListWorkflowSchedules')
        self.assertFalse(req.HasField('pageSize'))
        self.assertFalse(req.HasField('continuationToken'))
        self.assertEqual(WorkflowSchedulePage(schedules=[], continuation_token=None), page)

    def test_list_rejects_a_zero_page_size(self):
        """The runtime pages schedules like instance IDs, so 0 reaches the state store."""
        with self.assertRaises(ValueError):
            self.client.list_workflow_schedules(page_size=0)

        self.stub.ListWorkflowSchedules.assert_not_called()

    def test_delete_sends_the_name(self):
        self.client.delete_workflow_schedule('nightly')

        self.assertEqual('nightly', self.sent('DeleteWorkflowSchedule').name)

    def test_trigger_returns_the_run_instance_id(self):
        self.stub.TriggerWorkflowSchedule.return_value = pb.TriggerWorkflowScheduleResponse(
            instanceId='nightly_20261029T093000Z_manual'
        )

        instance_id = self.client.trigger_workflow_schedule('nightly')

        self.assertEqual('nightly', self.sent('TriggerWorkflowSchedule').name)
        self.assertEqual('nightly_20261029T093000Z_manual', instance_id)

    def test_listing_instances_forwards_the_id_prefix(self):
        self.stub.ListInstanceIDs.return_value = pb.ListInstanceIDsResponse(
            instanceIds=['nightly_20261029T093000Z']
        )

        ids = list(self.client.iter_workflow_instance_ids(instance_id_prefix='nightly_'))

        self.assertEqual(['nightly_20261029T093000Z'], ids)
        self.assertEqual('nightly_', self.sent('ListInstanceIDs').instanceIdPrefix)

    def test_listing_instances_leaves_the_prefix_unset_by_default(self):
        self.stub.ListInstanceIDs.return_value = pb.ListInstanceIDsResponse()

        self.client.list_workflow_instance_ids()

        self.assertFalse(self.sent('ListInstanceIDs').HasField('instanceIdPrefix'))


class AsyncWorkflowScheduleClientTest(unittest.IsolatedAsyncioTestCase):
    """The async client builds the same requests through its own stub calls."""

    def setUp(self):
        self.stub = mock.AsyncMock()
        stub_patch = mock.patch.object(stubs, 'TaskHubSidecarServiceStub', return_value=self.stub)
        channel_patch = mock.patch('dapr.ext.workflow._durabletask.aio.client.get_grpc_aio_channel')
        for patcher in (stub_patch, channel_patch):
            patcher.start()
            self.addCleanup(patcher.stop)
        self.client = AsyncWorkflowClient()

    def sent(self, method: str):
        return getattr(self.stub, method).call_args[0][0]

    async def test_create_sends_the_schedule(self):
        await self.client.create_workflow_schedule(
            'nightly',
            report_workflow,
            '@every 1h',
            input='eu',
            repeats=2,
            overwrite=True,
            skip_missed=True,
        )

        req = self.sent('CreateWorkflowSchedule')
        self.assertTrue(req.overwrite)
        self.assertEqual('report_workflow', req.schedule.workflowName)
        self.assertEqual('@every 1h', req.schedule.schedule)
        self.assertEqual('"eu"', req.schedule.input.value)
        self.assertEqual(2, req.schedule.repeats)
        self.assertTrue(req.schedule.skipMissed)

    async def test_get_returns_the_converted_schedule(self):
        self.stub.GetWorkflowSchedule.return_value = pb.GetWorkflowScheduleResponse(
            schedule=new_schedule_proto()
        )

        schedule = await self.client.get_workflow_schedule('nightly')

        self.assertEqual(WorkflowSchedule._from_proto(new_schedule_proto()), schedule)

    async def test_list_converts_the_page(self):
        self.stub.ListWorkflowSchedules.return_value = pb.ListWorkflowSchedulesResponse(
            schedules=[new_schedule_proto()]
        )

        page = await self.client.list_workflow_schedules(page_size=5)

        self.assertEqual(5, self.sent('ListWorkflowSchedules').pageSize)
        self.assertEqual(['nightly'], [schedule.name for schedule in page.schedules])
        self.assertIsNone(page.continuation_token)

    async def test_delete_sends_the_name(self):
        await self.client.delete_workflow_schedule('nightly')

        self.assertEqual('nightly', self.sent('DeleteWorkflowSchedule').name)

    async def test_trigger_returns_the_run_instance_id(self):
        self.stub.TriggerWorkflowSchedule.return_value = pb.TriggerWorkflowScheduleResponse(
            instanceId='nightly_20261029T093000Z_manual'
        )

        self.assertEqual(
            'nightly_20261029T093000Z_manual',
            await self.client.trigger_workflow_schedule('nightly'),
        )

    async def test_iterating_instances_forwards_the_id_prefix(self):
        self.stub.ListInstanceIDs.return_value = pb.ListInstanceIDsResponse(instanceIds=['a_1'])

        ids = [
            instance_id
            async for instance_id in self.client.iter_workflow_instance_ids(instance_id_prefix='a_')
        ]

        self.assertEqual(['a_1'], ids)
        self.assertEqual('a_', self.sent('ListInstanceIDs').instanceIdPrefix)
