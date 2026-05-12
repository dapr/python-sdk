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
from unittest import mock

import dapr.ext.workflow._durabletask.internal.protos as pb
from dapr.ext.workflow import PropagatedHistory
from dapr.ext.workflow._durabletask import task
from dapr.ext.workflow.workflow_activity_context import WorkflowActivityContext

mock_orchestration_id = 'orchestration001'
mock_task = 10


class FakeActivityContext:
    def __init__(self, propagated_history=None):
        self._propagated_history = propagated_history

    @property
    def orchestration_id(self):
        return mock_orchestration_id

    @property
    def task_id(self):
        return mock_task

    def get_propagated_history(self):
        return self._propagated_history


class WorkflowActivityContextTest(unittest.TestCase):
    def test_workflow_activity_context(self):
        with mock.patch(
            'dapr.ext.workflow._durabletask.task.ActivityContext',
            return_value=FakeActivityContext(),
        ):
            fake_act_ctx = task.ActivityContext(
                orchestration_id=mock_orchestration_id, task_id=mock_task
            )
            act_ctx = WorkflowActivityContext(fake_act_ctx)
            actual_orchestration_id = act_ctx.workflow_id
            assert actual_orchestration_id == mock_orchestration_id

            actual_task_id = act_ctx.task_id
            assert actual_task_id == mock_task

    def test_workflow_activity_context_get_propagated_history(self):
        history_proto = pb.PropagatedHistory(
            scope=pb.HISTORY_PROPAGATION_SCOPE_OWN_HISTORY,
            chunks=[
                pb.PropagatedHistoryChunk(
                    appId='caller-app',
                    instanceId='caller-instance',
                    workflowName='Caller',
                    rawEvents=[
                        pb.HistoryEvent(
                            eventId=0,
                            executionStarted=pb.ExecutionStartedEvent(name='Caller'),
                        ).SerializeToString(),
                    ],
                ),
            ],
        )
        propagated = PropagatedHistory.from_proto(history_proto)
        fake = FakeActivityContext(propagated_history=propagated)
        act_ctx = WorkflowActivityContext(fake)

        history = act_ctx.get_propagated_history()
        assert history is not None
        assert history.get_app_ids() == ['caller-app']

    def test_workflow_activity_context_get_propagated_history_default_none(self):
        fake = FakeActivityContext()
        act_ctx = WorkflowActivityContext(fake)
        assert act_ctx.get_propagated_history() is None
