import unittest
from unittest import mock
from durabletask import task
from dapr.ext.workflow.workflow_activity_context import WorkflowActivityContext

mock_orchestration_id = "orchestration001"
mock_task = 10

class FakeActivityContext:
    @property
    def orchestration_id(self):
        return mock_orchestration_id
    
    @property
    def task_id(self):
        return mock_task

class WorkflowActivityContextTest(unittest.TestCase):
    def test_workflow_activity_context(self):
        with mock.patch('durabletask.task.ActivityContext', return_value = FakeActivityContext()):
            fake_act_ctx = task.ActivityContext(orchestration_id=mock_orchestration_id, task_id=mock_task)
            act_ctx = WorkflowActivityContext(fake_act_ctx)
            actual_orchestration_id = act_ctx.workflow_id()
            assert actual_orchestration_id == mock_orchestration_id

            actual_task_id = act_ctx.task_id()
            assert actual_task_id == mock_task
