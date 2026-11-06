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

"""The workflow clients report whether the sidecar staged an operation.

A fake sidecar runs on a real gRPC server and answers with ``staged`` set as the
test asks, so the requests and responses cross the wire.
"""

import unittest
from concurrent import futures
from unittest import mock

import grpc

import dapr.ext.workflow._durabletask.internal.orchestrator_service_pb2_grpc as stubs
import dapr.ext.workflow._durabletask.internal.protos as pb
from dapr.conf import settings
from dapr.ext.workflow import (
    DaprWorkflowClient,
    WorkflowOperationResult,
    WorkflowRerunResult,
    WorkflowScheduleResult,
)
from dapr.ext.workflow.aio import DaprWorkflowClient as AsyncDaprWorkflowClient

INSTANCE_ID = 'instance001'
NEW_INSTANCE_ID = 'instance002'
TARGET_APP_ID = 'appB'


class _StagingSidecar(stubs.TaskHubSidecarServiceServicer):
    """Answers every operation that can be staged with ``staged`` set to ``self.staged``."""

    def __init__(self) -> None:
        self.staged = False
        self.requests: dict[str, object] = {}

    def StartInstance(  # noqa: N802
        self, request: pb.CreateInstanceRequest, context: grpc.ServicerContext
    ) -> pb.CreateInstanceResponse:
        self.requests['StartInstance'] = request
        return pb.CreateInstanceResponse(instanceId=request.instanceId, staged=self.staged)

    def RaiseEvent(  # noqa: N802
        self, request: pb.RaiseEventRequest, context: grpc.ServicerContext
    ) -> pb.RaiseEventResponse:
        self.requests['RaiseEvent'] = request
        return pb.RaiseEventResponse(staged=self.staged)

    def TerminateInstance(  # noqa: N802
        self, request: pb.TerminateRequest, context: grpc.ServicerContext
    ) -> pb.TerminateResponse:
        self.requests['TerminateInstance'] = request
        return pb.TerminateResponse(staged=self.staged)

    def SuspendInstance(  # noqa: N802
        self, request: pb.SuspendRequest, context: grpc.ServicerContext
    ) -> pb.SuspendResponse:
        self.requests['SuspendInstance'] = request
        return pb.SuspendResponse(staged=self.staged)

    def ResumeInstance(  # noqa: N802
        self, request: pb.ResumeRequest, context: grpc.ServicerContext
    ) -> pb.ResumeResponse:
        self.requests['ResumeInstance'] = request
        return pb.ResumeResponse(staged=self.staged)

    def RerunWorkflowFromEvent(  # noqa: N802
        self, request: pb.RerunWorkflowFromEventRequest, context: grpc.ServicerContext
    ) -> pb.RerunWorkflowFromEventResponse:
        self.requests['RerunWorkflowFromEvent'] = request
        return pb.RerunWorkflowFromEventResponse(
            newInstanceID=request.newInstanceID, staged=self.staged
        )


class _SidecarTestMixin:
    """Starts a fake sidecar on a free local port for each test."""

    def start_sidecar(self) -> tuple[_StagingSidecar, str]:
        sidecar = _StagingSidecar()
        server = grpc.server(futures.ThreadPoolExecutor(max_workers=2))
        stubs.add_TaskHubSidecarServiceServicer_to_server(sidecar, server)
        port = server.add_insecure_port('127.0.0.1:0')
        server.start()
        self.addCleanup(server.stop, None)  # type: ignore[attr-defined]
        return sidecar, str(port)


@mock.patch.object(settings, 'DAPR_API_TOKEN', None)
class StagedOperationsTest(_SidecarTestMixin, unittest.TestCase):
    def setUp(self) -> None:
        self.sidecar, port = self.start_sidecar()
        self.wf_client = DaprWorkflowClient(host='127.0.0.1', port=port)
        self.addCleanup(self.wf_client.close)

    def test_each_operation_reports_whether_the_sidecar_staged_it(self) -> None:
        for staged in (True, False):
            with self.subTest(staged=staged):
                self.sidecar.staged = staged

                schedule_result = self.wf_client.schedule_new_workflow_with_result(
                    'wf', instance_id=INSTANCE_ID
                )
                self.assertEqual(WorkflowScheduleResult(INSTANCE_ID, staged), schedule_result)

                raise_result = self.wf_client.raise_workflow_event_with_result(
                    INSTANCE_ID, 'approval', data={'ok': True}
                )
                self.assertEqual(WorkflowOperationResult(staged), raise_result)

                terminate_result = self.wf_client.terminate_workflow_with_result(INSTANCE_ID)
                self.assertEqual(WorkflowOperationResult(staged), terminate_result)

                pause_result = self.wf_client.pause_workflow_with_result(INSTANCE_ID)
                self.assertEqual(WorkflowOperationResult(staged), pause_result)

                resume_result = self.wf_client.resume_workflow_with_result(INSTANCE_ID)
                self.assertEqual(WorkflowOperationResult(staged), resume_result)

                rerun_result = self.wf_client.rerun_workflow_from_event_with_result(
                    INSTANCE_ID, 3, new_instance_id=NEW_INSTANCE_ID
                )
                self.assertEqual(WorkflowRerunResult(NEW_INSTANCE_ID, staged), rerun_result)

    def test_result_methods_send_the_same_requests_as_the_plain_ones(self) -> None:
        self.wf_client.schedule_new_workflow_with_result(
            'wf', input={'n': 1}, instance_id=INSTANCE_ID, app_id=TARGET_APP_ID
        )
        start_request = self.sidecar.requests['StartInstance']
        self.wf_client.schedule_new_workflow(
            'wf', input={'n': 1}, instance_id=INSTANCE_ID, app_id=TARGET_APP_ID
        )
        self.assertEqual(start_request, self.sidecar.requests['StartInstance'])

        self.wf_client.terminate_workflow_with_result(
            INSTANCE_ID, output='done', recursive=False, app_id=TARGET_APP_ID
        )
        terminate_request = self.sidecar.requests['TerminateInstance']
        self.wf_client.terminate_workflow(
            INSTANCE_ID, output='done', recursive=False, app_id=TARGET_APP_ID
        )
        self.assertEqual(terminate_request, self.sidecar.requests['TerminateInstance'])

        self.wf_client.rerun_workflow_from_event_with_result(INSTANCE_ID, 3, input=None)
        rerun_request = self.sidecar.requests['RerunWorkflowFromEvent']
        self.assertTrue(rerun_request.overwriteInput)
        self.wf_client.rerun_workflow_from_event(INSTANCE_ID, 3, input=None)
        self.assertEqual(rerun_request, self.sidecar.requests['RerunWorkflowFromEvent'])

    def test_plain_methods_keep_their_return_values_when_staged(self) -> None:
        self.sidecar.staged = True

        instance_id = self.wf_client.schedule_new_workflow('wf', instance_id=INSTANCE_ID)
        self.assertEqual(INSTANCE_ID, instance_id)
        self.assertIsNone(self.wf_client.raise_workflow_event(INSTANCE_ID, 'approval'))
        self.assertIsNone(self.wf_client.terminate_workflow(INSTANCE_ID))
        self.assertIsNone(self.wf_client.pause_workflow(INSTANCE_ID))
        self.assertIsNone(self.wf_client.resume_workflow(INSTANCE_ID))
        new_instance_id = self.wf_client.rerun_workflow_from_event(
            INSTANCE_ID, 3, new_instance_id=NEW_INSTANCE_ID
        )
        self.assertEqual(NEW_INSTANCE_ID, new_instance_id)


@mock.patch.object(settings, 'DAPR_API_TOKEN', None)
class AsyncStagedOperationsTest(_SidecarTestMixin, unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.sidecar, port = self.start_sidecar()
        self.wf_client = AsyncDaprWorkflowClient(host='127.0.0.1', port=port)
        # The async workflow client has no public close; close its channel directly.
        self.addAsyncCleanup(self.wf_client._DaprWorkflowClient__obj.aclose)

    async def test_each_operation_reports_whether_the_sidecar_staged_it(self) -> None:
        for staged in (True, False):
            with self.subTest(staged=staged):
                self.sidecar.staged = staged

                schedule_result = await self.wf_client.schedule_new_workflow_with_result(
                    'wf', instance_id=INSTANCE_ID
                )
                self.assertEqual(WorkflowScheduleResult(INSTANCE_ID, staged), schedule_result)

                raise_result = await self.wf_client.raise_workflow_event_with_result(
                    INSTANCE_ID, 'approval', data={'ok': True}
                )
                self.assertEqual(WorkflowOperationResult(staged), raise_result)

                terminate_result = await self.wf_client.terminate_workflow_with_result(INSTANCE_ID)
                self.assertEqual(WorkflowOperationResult(staged), terminate_result)

                pause_result = await self.wf_client.pause_workflow_with_result(INSTANCE_ID)
                self.assertEqual(WorkflowOperationResult(staged), pause_result)

                resume_result = await self.wf_client.resume_workflow_with_result(INSTANCE_ID)
                self.assertEqual(WorkflowOperationResult(staged), resume_result)

                rerun_result = await self.wf_client.rerun_workflow_from_event_with_result(
                    INSTANCE_ID, 3, new_instance_id=NEW_INSTANCE_ID
                )
                self.assertEqual(WorkflowRerunResult(NEW_INSTANCE_ID, staged), rerun_result)

    async def test_plain_methods_keep_their_return_values_when_staged(self) -> None:
        self.sidecar.staged = True

        instance_id = await self.wf_client.schedule_new_workflow('wf', instance_id=INSTANCE_ID)
        self.assertEqual(INSTANCE_ID, instance_id)
        self.assertIsNone(await self.wf_client.raise_workflow_event(INSTANCE_ID, 'approval'))
        self.assertIsNone(await self.wf_client.terminate_workflow(INSTANCE_ID))
        self.assertIsNone(await self.wf_client.pause_workflow(INSTANCE_ID))
        self.assertIsNone(await self.wf_client.resume_workflow(INSTANCE_ID))
        new_instance_id = await self.wf_client.rerun_workflow_from_event(
            INSTANCE_ID, 3, new_instance_id=NEW_INSTANCE_ID
        )
        self.assertEqual(NEW_INSTANCE_ID, new_instance_id)


if __name__ == '__main__':
    unittest.main()
