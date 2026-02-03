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
from typing import List
from unittest import mock

from dapr.ext.workflow.dapr_workflow_context import DaprWorkflowContext
from dapr.ext.workflow.logger import Logger
from dapr.ext.workflow.workflow_activity_context import WorkflowActivityContext
from dapr.ext.workflow.workflow_runtime import WorkflowRuntime, alternate_name

listOrchestrators: List[str] = []
listActivities: List[str] = []


class FakeTaskHubGrpcWorker:
    def __init__(self):
        self._orchestrator_fns = {}
        self._activity_fns = {}

    def add_named_orchestrator(self, name: str, fn):
        listOrchestrators.append(name)
        self._orchestrator_fns[name] = fn

    def add_named_activity(self, name: str, fn):
        listActivities.append(name)
        self._activity_fns[name] = fn


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


class WorkflowRuntimeWorkerReadyTest(unittest.TestCase):
    """Tests for wait_for_worker_ready() and start() stream readiness."""

    def setUp(self):
        listActivities.clear()
        listOrchestrators.clear()
        mock.patch('durabletask.worker._Registry', return_value=FakeTaskHubGrpcWorker()).start()
        self.runtime = WorkflowRuntime()

    def test_wait_for_worker_ready_returns_false_when_no_is_worker_ready(self):
        mock_worker = mock.MagicMock(spec=['start', 'stop', '_registry'])
        del mock_worker.is_worker_ready
        self.runtime._WorkflowRuntime__worker = mock_worker
        self.assertFalse(self.runtime.wait_for_worker_ready(timeout=0.1))

    def test_wait_for_worker_ready_returns_true_when_ready(self):
        mock_worker = mock.MagicMock()
        mock_worker.is_worker_ready.return_value = True
        self.runtime._WorkflowRuntime__worker = mock_worker
        self.assertTrue(self.runtime.wait_for_worker_ready(timeout=1.0))
        mock_worker.is_worker_ready.assert_called()

    def test_wait_for_worker_ready_returns_false_on_timeout(self):
        mock_worker = mock.MagicMock()
        mock_worker.is_worker_ready.return_value = False
        self.runtime._WorkflowRuntime__worker = mock_worker
        self.assertFalse(self.runtime.wait_for_worker_ready(timeout=0.2))

    def test_start_succeeds_when_worker_ready(self):
        mock_worker = mock.MagicMock()
        mock_worker.is_worker_ready.return_value = True
        self.runtime._WorkflowRuntime__worker = mock_worker
        self.runtime.start()
        mock_worker.start.assert_called_once()
        mock_worker.is_worker_ready.assert_called()

    def test_start_raises_when_worker_not_ready(self):
        listActivities.clear()
        listOrchestrators.clear()
        mock.patch('durabletask.worker._Registry', return_value=FakeTaskHubGrpcWorker()).start()
        runtime = WorkflowRuntime(worker_ready_timeout=0.2)
        mock_worker = mock.MagicMock()
        mock_worker.is_worker_ready.return_value = False
        runtime._WorkflowRuntime__worker = mock_worker
        with self.assertRaises(RuntimeError) as ctx:
            runtime.start()
        self.assertIn('not ready', str(ctx.exception))

    def test_start_logs_warning_when_no_is_worker_ready(self):
        mock_worker = mock.MagicMock(spec=['start', 'stop', '_registry'])
        del mock_worker.is_worker_ready
        self.runtime._WorkflowRuntime__worker = mock_worker
        self.runtime.start()
        mock_worker.start.assert_called_once()

    def test_worker_ready_timeout_init(self):
        listActivities.clear()
        listOrchestrators.clear()
        mock.patch('durabletask.worker._Registry', return_value=FakeTaskHubGrpcWorker()).start()
        rt = WorkflowRuntime(worker_ready_timeout=15.0)
        self.assertEqual(rt._worker_ready_timeout, 15.0)

    def test_start_raises_when_worker_start_fails(self):
        mock_worker = mock.MagicMock()
        mock_worker.is_worker_ready.return_value = True
        mock_worker.start.side_effect = RuntimeError('start failed')
        self.runtime._WorkflowRuntime__worker = mock_worker
        with self.assertRaises(RuntimeError) as ctx:
            self.runtime.start()
        self.assertIn('start failed', str(ctx.exception))
        mock_worker.start.assert_called_once()

    def test_start_raises_when_wait_for_worker_ready_raises(self):
        mock_worker = mock.MagicMock()
        mock_worker.start.return_value = None
        mock_worker.is_worker_ready.side_effect = ValueError('ready check failed')
        self.runtime._WorkflowRuntime__worker = mock_worker
        with self.assertRaises(ValueError) as ctx:
            self.runtime.start()
        self.assertIn('ready check failed', str(ctx.exception))

    def test_shutdown_raises_when_worker_stop_fails(self):
        mock_worker = mock.MagicMock()
        mock_worker.stop.side_effect = RuntimeError('stop failed')
        self.runtime._WorkflowRuntime__worker = mock_worker
        with self.assertRaises(RuntimeError) as ctx:
            self.runtime.shutdown()
        self.assertIn('stop failed', str(ctx.exception))

