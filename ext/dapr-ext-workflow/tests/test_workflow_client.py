# -*- coding: utf-8 -*-

"""
Copyright 2023 The Dapr Authors
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

from datetime import datetime
from typing import Any, Union
import unittest
from dapr.ext.workflow.dapr_workflow_context import DaprWorkflowContext
from unittest import mock
from dapr.ext.workflow.dapr_workflow_client import DaprWorkflowClient
from durabletask import client
import durabletask.internal.orchestrator_service_pb2 as pb
from grpc import RpcError

mock_schedule_result = 'workflow001'
mock_raise_event_result = 'event001'
mock_terminate_result = 'terminate001'
mock_suspend_result = 'suspend001'
mock_resume_result = 'resume001'
mock_purge_result = 'purge001'
mock_instance_id = 'instance001'
wf_status = 'not-found'


class SimulatedRpcError(RpcError):
    def __init__(self, code, details):
        self._code = code
        self._details = details

    def code(self):
        return self._code

    def details(self):
        return self._details


class FakeTaskHubGrpcClient:
    def schedule_new_orchestration(
        self,
        workflow,
        input,
        instance_id,
        start_at,
        reuse_id_policy: Union[pb.OrchestrationIdReusePolicy, None] = None,
    ):
        return mock_schedule_result

    def get_orchestration_state(self, instance_id, fetch_payloads):
        if wf_status == 'not-found':
            raise SimulatedRpcError(code='UNKNOWN', details='no such instance exists')
        elif wf_status == 'found':
            return self._inner_get_orchestration_state(
                instance_id, client.OrchestrationStatus.PENDING
            )
        else:
            raise SimulatedRpcError(code='UNKNOWN', details='unknown error')

    def wait_for_orchestration_start(self, instance_id, fetch_payloads, timeout):
        return self._inner_get_orchestration_state(instance_id, client.OrchestrationStatus.RUNNING)

    def wait_for_orchestration_completion(self, instance_id, fetch_payloads, timeout):
        return self._inner_get_orchestration_state(
            instance_id, client.OrchestrationStatus.COMPLETED
        )

    def raise_orchestration_event(
        self, instance_id: str, event_name: str, *, data: Union[Any, None] = None
    ):
        return mock_raise_event_result

    def terminate_orchestration(
        self, instance_id: str, *, output: Union[Any, None] = None, recursive: bool = True
    ):
        return mock_terminate_result

    def suspend_orchestration(self, instance_id: str):
        return mock_suspend_result

    def resume_orchestration(self, instance_id: str):
        return mock_resume_result

    def purge_orchestration(self, instance_id: str, recursive: bool = True):
        return mock_purge_result

    def _inner_get_orchestration_state(self, instance_id, state: client.OrchestrationStatus):
        return client.OrchestrationState(
            instance_id=instance_id,
            name='',
            runtime_status=state,
            created_at=datetime.now(),
            last_updated_at=datetime.now(),
            serialized_input=None,
            serialized_output=None,
            serialized_custom_status=None,
            failure_details=None,
        )


class WorkflowClientTest(unittest.TestCase):
    def mock_client_wf(ctx: DaprWorkflowContext, input):
        print(f'{input}')

    def test_client_functions(self):
        with mock.patch(
            'durabletask.client.TaskHubGrpcClient', return_value=FakeTaskHubGrpcClient()
        ):
            wfClient = DaprWorkflowClient()
            actual_schedule_result = wfClient.schedule_new_workflow(
                workflow=self.mock_client_wf, input='Hi Chef!'
            )
            assert actual_schedule_result == mock_schedule_result

            global wf_status
            wf_status = 'not-found'
            actual_get_result = wfClient.get_workflow_state(
                instance_id=mock_instance_id, fetch_payloads=True
            )
            assert actual_get_result is None

            wf_status = 'error'
            with self.assertRaises(RpcError):
                wfClient.get_workflow_state(instance_id=mock_instance_id, fetch_payloads=True)

            assert actual_get_result is None

            wf_status = 'found'
            actual_get_result = wfClient.get_workflow_state(
                instance_id=mock_instance_id, fetch_payloads=True
            )
            assert actual_get_result.runtime_status.name == 'PENDING'
            assert actual_get_result.instance_id == mock_instance_id

            actual_wait_start_result = wfClient.wait_for_workflow_start(
                instance_id=mock_instance_id, timeout_in_seconds=30
            )
            assert actual_wait_start_result.runtime_status.name == 'RUNNING'
            assert actual_wait_start_result.instance_id == mock_instance_id

            actual_wait_completion_result = wfClient.wait_for_workflow_completion(
                instance_id=mock_instance_id, timeout_in_seconds=30
            )
            assert actual_wait_completion_result.runtime_status.name == 'COMPLETED'
            assert actual_wait_completion_result.instance_id == mock_instance_id

            actual_raise_event_result = wfClient.raise_workflow_event(
                instance_id=mock_instance_id, event_name='test_event', data='test_data'
            )
            assert actual_raise_event_result == mock_raise_event_result

            actual_terminate_result = wfClient.terminate_workflow(
                instance_id=mock_instance_id, output='test_output'
            )
            assert actual_terminate_result == mock_terminate_result

            actual_suspend_result = wfClient.pause_workflow(instance_id=mock_instance_id)
            assert actual_suspend_result == mock_suspend_result

            actual_resume_result = wfClient.resume_workflow(instance_id=mock_instance_id)
            assert actual_resume_result == mock_resume_result

            actual_purge_result = wfClient.purge_workflow(instance_id=mock_instance_id)
            assert actual_purge_result == mock_purge_result
