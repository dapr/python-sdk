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

from typing import List
import unittest
from dapr.ext.workflow.dapr_workflow_context import DaprWorkflowContext
from unittest import mock
from dapr.ext.workflow.workflow_runtime import WorkflowRuntime
from dapr.ext.workflow.workflow_activity_context import WorkflowActivityContext

listOrchestrators: List[str] = []
listActivities: List[str] = []


class FakeTaskHubGrpcWorker:
    def add_named_orchestrator(self, name: str, fn):
        listOrchestrators.append(name)

    def add_named_activity(self, name: str, fn):
        listActivities.append(name)


class WorkflowRuntimeTest(unittest.TestCase):
    def mock_client_wf(ctx: DaprWorkflowContext, input):
        print(f'{input}')

    def mock_client_activity(ctx: WorkflowActivityContext, input):
        print(f'{input}!', flush=True)

    def test_runtime_options(self):
        with mock.patch('durabletask.worker._Registry', return_value=FakeTaskHubGrpcWorker()):
            runtime_options = WorkflowRuntime()

            runtime_options.register_workflow(self.mock_client_wf)
            wanted_orchestrator = [self.mock_client_wf.__name__]
            assert listOrchestrators == wanted_orchestrator

            runtime_options.register_activity(self.mock_client_activity)
            wanted_activity = [self.mock_client_activity.__name__]
            assert listActivities == wanted_activity
