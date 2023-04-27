from typing import List
import unittest
from dapr.ext.workflow.dapr_workflow_context import DaprWorkflowContext
from unittest import mock
from dapr.ext.workflow.workflow_runtime_options import WorkflowRuntimeOptions
from dapr.ext.workflow.workflow_activity_context import WorkflowActivityContext

listOrchestrators: List[str] = list[str]()
listActivities: List[str] = list[str]()


class FakeTaskHubGrpcWorker:
    def add_named_orchestrator(self, name: str, fn):
        listOrchestrators.append(name)

    def add_named_activity(self, name: str, fn):
        listActivities.append(name)


class WorkflowRuntimeOptionsTest(unittest.TestCase):

    def mock_client_wf(ctx: DaprWorkflowContext, input):
        print(f'{input}')

    def mock_client_activity(ctx: WorkflowActivityContext, input):
        print(f'{input}!', flush=True)

    def test_runtime_options(self):
        with mock.patch('durabletask.worker._Registry', return_value=FakeTaskHubGrpcWorker()):
            runtime_options = WorkflowRuntimeOptions()

            runtime_options.register_workflow(self.mock_client_wf)
            wanted_orchestrator = [self.mock_client_wf.__name__]
            assert listOrchestrators == wanted_orchestrator

            runtime_options.register_activity(self.mock_client_activity)
            wanted_activity = [self.mock_client_activity.__name__]
            assert listActivities == wanted_activity
