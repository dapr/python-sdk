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
from dapr.ext.workflow.workflow_runtime import WorkflowRuntime, alternate_name
from dapr.ext.workflow.workflow_activity_context import WorkflowActivityContext

listOrchestrators: List[str] = []
listActivities: List[str] = []


class FakeTaskHubGrpcWorker:
    def add_named_orchestrator(self, name: str, fn):
        listOrchestrators.append(name)

    def add_named_activity(self, name: str, fn):
        listActivities.append(name)


class WorkflowRuntimeTest(unittest.TestCase):
    def setUp(self):
        listActivities.clear()
        listOrchestrators.clear()
        mock.patch('durabletask.worker._Registry', return_value=FakeTaskHubGrpcWorker()).start()
        self.runtime_options = WorkflowRuntime()
        if hasattr(self.mock_client_wf, '_dapr_alternate_name'):
            del self.mock_client_wf.__dict__['_dapr_alternate_name']
        if hasattr(self.mock_client_activity, '_dapr_alternate_name'):
            del self.mock_client_activity.__dict__['_dapr_alternate_name']
        if hasattr(self.mock_client_wf, '_workflow_registered'):
            del self.mock_client_wf.__dict__['_workflow_registered']
        if hasattr(self.mock_client_activity, '_activity_registered'):
            del self.mock_client_activity.__dict__['_activity_registered']

    def mock_client_wf(ctx: DaprWorkflowContext, input):
        print(f'{input}')

    def mock_client_activity(ctx: WorkflowActivityContext, input):
        print(f'{input}!', flush=True)

    def test_register(self):
        self.runtime_options.register_workflow(self.mock_client_wf, name='mock_client_wf')
        wanted_orchestrator = [self.mock_client_wf.__name__]
        assert listOrchestrators == wanted_orchestrator
        assert self.mock_client_wf._dapr_alternate_name == 'mock_client_wf'
        assert self.mock_client_wf._workflow_registered

        self.runtime_options.register_activity(self.mock_client_activity)
        wanted_activity = [self.mock_client_activity.__name__]
        assert listActivities == wanted_activity
        assert self.mock_client_activity._activity_registered

    def test_decorator_register(self):
        client_wf = (self.runtime_options.workflow())(self.mock_client_wf)
        wanted_orchestrator = [self.mock_client_wf.__name__]
        assert listOrchestrators == wanted_orchestrator
        assert client_wf._dapr_alternate_name == self.mock_client_wf.__name__
        assert self.mock_client_wf._workflow_registered

        client_activity = (self.runtime_options.activity())(self.mock_client_activity)
        wanted_activity = [self.mock_client_activity.__name__]
        assert listActivities == wanted_activity
        assert client_activity._dapr_alternate_name == self.mock_client_activity.__name__
        assert self.mock_client_activity._activity_registered

    def test_both_decorator_and_register(self):
        client_wf = (self.runtime_options.workflow(name='test_wf'))(self.mock_client_wf)
        wanted_orchestrator = ['test_wf']
        assert listOrchestrators == wanted_orchestrator
        assert client_wf._dapr_alternate_name == 'test_wf'
        assert self.mock_client_wf._workflow_registered

        self.runtime_options.register_activity(self.mock_client_activity, name='test_act')
        wanted_activity = ['test_act']
        assert listActivities == wanted_activity
        assert hasattr(self.mock_client_activity, '_dapr_alternate_name')
        assert self.mock_client_activity._activity_registered

    def test_register_wf_act_using_both_decorator_and_method(self):
        client_wf = (self.runtime_options.workflow(name='test_wf'))(self.mock_client_wf)

        wanted_orchestrator = ['test_wf']
        assert listOrchestrators == wanted_orchestrator
        assert client_wf._dapr_alternate_name == 'test_wf'
        with self.assertRaises(ValueError) as exeception_context:
            self.runtime_options.register_workflow(self.mock_client_wf)
        wf_name = self.mock_client_wf.__name__
        self.assertEqual(
            exeception_context.exception.args[0],
            f'Workflow {wf_name} already registered as test_wf',
        )

        client_act = (self.runtime_options.activity(name='test_act'))(self.mock_client_activity)
        wanted_activity = ['test_act']
        assert listActivities == wanted_activity
        assert client_act._dapr_alternate_name == 'test_act'
        with self.assertRaises(ValueError) as exeception_context:
            self.runtime_options.register_activity(self.mock_client_activity)
        act_name = self.mock_client_activity.__name__
        self.assertEqual(
            exeception_context.exception.args[0],
            f'Activity {act_name} already registered as test_act',
        )

    def test_duplicate_dapr_alternate_name_registration(self):
        client_wf = (alternate_name(name='test'))(self.mock_client_wf)
        with self.assertRaises(ValueError) as exeception_context:
            (self.runtime_options.workflow(name='random'))(client_wf)
        self.assertEqual(
            exeception_context.exception.args[0],
            f'Workflow {client_wf.__name__} already has an alternate name test',
        )

        client_act = (alternate_name(name='test'))(self.mock_client_activity)
        with self.assertRaises(ValueError) as exeception_context:
            (self.runtime_options.activity(name='random'))(client_act)
        self.assertEqual(
            exeception_context.exception.args[0],
            f'Activity {client_act.__name__} already has an alternate name test',
        )

    def test_register_wf_act_using_both_decorator_and_method_without_name(self):
        client_wf = (self.runtime_options.workflow())(self.mock_client_wf)

        wanted_orchestrator = ['mock_client_wf']
        assert listOrchestrators == wanted_orchestrator
        assert client_wf._dapr_alternate_name == 'mock_client_wf'
        with self.assertRaises(ValueError) as exeception_context:
            self.runtime_options.register_workflow(self.mock_client_wf, name='test_wf')
        wf_name = self.mock_client_wf.__name__
        self.assertEqual(
            exeception_context.exception.args[0],
            f'Workflow {wf_name} already registered as mock_client_wf',
        )

        client_act = (self.runtime_options.activity())(self.mock_client_activity)
        wanted_activity = ['mock_client_activity']
        assert listActivities == wanted_activity
        assert client_act._dapr_alternate_name == 'mock_client_activity'
        with self.assertRaises(ValueError) as exeception_context:
            self.runtime_options.register_activity(self.mock_client_activity, name='test_act')
        act_name = self.mock_client_activity.__name__
        self.assertEqual(
            exeception_context.exception.args[0],
            f'Activity {act_name} already registered as mock_client_activity',
        )

    def test_decorator_register_optinal_name(self):
        client_wf = (self.runtime_options.workflow(name='test_wf'))(self.mock_client_wf)
        wanted_orchestrator = ['test_wf']
        assert listOrchestrators == wanted_orchestrator
        assert client_wf._dapr_alternate_name == 'test_wf'

        client_act = (self.runtime_options.activity(name='test_act'))(self.mock_client_activity)
        wanted_activity = ['test_act']
        assert listActivities == wanted_activity
        assert client_act._dapr_alternate_name == 'test_act'
