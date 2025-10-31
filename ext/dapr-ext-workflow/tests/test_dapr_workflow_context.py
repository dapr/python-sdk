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

import unittest
from datetime import datetime
from unittest import mock

from dapr.ext.workflow.dapr_workflow_context import DaprWorkflowContext
from dapr.ext.workflow.workflow_activity_context import WorkflowActivityContext
from durabletask import worker

mock_date_time = datetime(2023, 4, 27)
mock_instance_id = 'instance001'
mock_create_timer = 'create_timer'
mock_call_activity = 'call_activity'
mock_call_sub_orchestrator = 'call_sub_orchestrator'
mock_custom_status = 'custom_status'


class FakeOrchestrationContext:
    def __init__(self):
        self.instance_id = mock_instance_id
        self.custom_status = None

    def create_timer(self, fire_at):
        return mock_create_timer

    def call_activity(self, activity, input, app_id):
        return mock_call_activity

    def call_sub_orchestrator(self, orchestrator, input, instance_id, app_id):
        return mock_call_sub_orchestrator

    def set_custom_status(self, custom_status):
        self.custom_status = custom_status


class DaprWorkflowContextTest(unittest.TestCase):
    def mock_client_activity(ctx: WorkflowActivityContext, input):
        print(f'{input}!', flush=True)

    def mock_client_child_wf(ctx: DaprWorkflowContext, input):
        print(f'{input}')

    def test_workflow_context_functions(self):
        with mock.patch(
            'durabletask.worker._RuntimeOrchestrationContext',
            return_value=FakeOrchestrationContext(),
        ):
            fakeContext = worker._RuntimeOrchestrationContext(mock_instance_id)
            dapr_wf_ctx = DaprWorkflowContext(fakeContext)
            call_activity_result = dapr_wf_ctx.call_activity(self.mock_client_activity, input=None)
            assert call_activity_result == mock_call_activity

            call_sub_orchestrator_result = dapr_wf_ctx.call_child_workflow(
                self.mock_client_child_wf
            )
            assert call_sub_orchestrator_result == mock_call_sub_orchestrator

            create_timer_result = dapr_wf_ctx.create_timer(mock_date_time)
            assert create_timer_result == mock_create_timer

            dapr_wf_ctx.set_custom_status(mock_custom_status)
            assert fakeContext.custom_status == mock_custom_status
