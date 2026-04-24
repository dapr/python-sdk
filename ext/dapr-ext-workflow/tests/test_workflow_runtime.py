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
from typing import List, Optional
from unittest import mock

import grpc
from pydantic import BaseModel, ValidationError

from dapr.ext.workflow.dapr_workflow_context import DaprWorkflowContext
from dapr.ext.workflow.workflow_activity_context import WorkflowActivityContext
from dapr.ext.workflow.workflow_runtime import WorkflowRuntime, alternate_name


class Order(BaseModel):
    order_id: str
    amount: float


listOrchestrators: List[str] = []
listActivities: List[str] = []


class FakeTaskHubGrpcWorker:
    def __init__(self):
        self._orchestrator_fns = {}
        self._activity_fns = {}

    def add_named_orchestrator(self, name: str, fn, **kwargs):
        listOrchestrators.append(name)
        self._orchestrator_fns[name] = fn

    def add_named_activity(self, name: str, fn):
        listActivities.append(name)
        self._activity_fns[name] = fn


class WorkflowRuntimeTimeoutInterceptorTest(unittest.TestCase):
    def setUp(self):
        listActivities.clear()
        listOrchestrators.clear()
        self._registry_patch = mock.patch(
            'durabletask.worker._Registry', return_value=FakeTaskHubGrpcWorker()
        )
        self._registry_patch.start()

    def tearDown(self):
        mock.patch.stopall()

    def test_timeout_interceptor_is_prepended(self):
        with mock.patch('durabletask.worker.TaskHubGrpcWorker') as mock_worker_cls:
            WorkflowRuntime()
            mock_worker_cls.assert_called_once()
            call_kwargs = mock_worker_cls.call_args[1]
            interceptors = call_kwargs['interceptors']
            self.assertEqual(len(interceptors), 1)
            from dapr.clients.grpc.interceptors import \
                DaprClientTimeoutInterceptor

            self.assertIsInstance(interceptors[0], DaprClientTimeoutInterceptor)

    def test_timeout_interceptor_with_custom_interceptors(self):
        custom_interceptor = mock.MagicMock(spec=grpc.UnaryUnaryClientInterceptor)
        with mock.patch('durabletask.worker.TaskHubGrpcWorker') as mock_worker_cls:
            WorkflowRuntime(interceptors=[custom_interceptor])
            call_kwargs = mock_worker_cls.call_args[1]
            interceptors = call_kwargs['interceptors']
            self.assertEqual(len(interceptors), 2)
            from dapr.clients.grpc.interceptors import \
                DaprClientTimeoutInterceptor

            self.assertIsInstance(interceptors[0], DaprClientTimeoutInterceptor)
            self.assertIs(interceptors[1], custom_interceptor)

    def test_timeout_interceptor_preserves_custom_interceptor_order(self):
        custom1 = mock.MagicMock(spec=grpc.UnaryUnaryClientInterceptor)
        custom2 = mock.MagicMock(spec=grpc.UnaryStreamClientInterceptor)
        with mock.patch('durabletask.worker.TaskHubGrpcWorker') as mock_worker_cls:
            WorkflowRuntime(interceptors=[custom1, custom2])
            call_kwargs = mock_worker_cls.call_args[1]
            interceptors = call_kwargs['interceptors']
            self.assertEqual(len(interceptors), 3)
            from dapr.clients.grpc.interceptors import \
                DaprClientTimeoutInterceptor

            self.assertIsInstance(interceptors[0], DaprClientTimeoutInterceptor)
            self.assertIs(interceptors[1], custom1)
            self.assertIs(interceptors[2], custom2)


class WorkflowRuntimeTest(unittest.TestCase):
    def setUp(self):
        listActivities.clear()
        listOrchestrators.clear()
        mock.patch(
            'dapr.ext.workflow._durabletask.worker._Registry', return_value=FakeTaskHubGrpcWorker()
        ).start()
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
        mock.patch(
            'dapr.ext.workflow._durabletask.worker._Registry', return_value=FakeTaskHubGrpcWorker()
        ).start()
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

    def test_wait_for_worker_ready_returns_true_after_poll(self):
        """Worker becomes ready on second poll."""
        mock_worker = mock.MagicMock()
        mock_worker.is_worker_ready.side_effect = [False, True]
        self.runtime._WorkflowRuntime__worker = mock_worker
        self.assertTrue(self.runtime.wait_for_worker_ready(timeout=1.0))
        self.assertEqual(mock_worker.is_worker_ready.call_count, 2)

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

    def test_start_logs_debug_when_worker_stream_ready(self):
        """start() logs at debug when worker and stream are ready."""
        mock_worker = mock.MagicMock()
        mock_worker.is_worker_ready.return_value = True
        self.runtime._WorkflowRuntime__worker = mock_worker
        with mock.patch.object(self.runtime._logger, 'debug') as mock_debug:
            self.runtime.start()
        mock_debug.assert_called_once()
        call_args = mock_debug.call_args[0][0]
        self.assertIn('ready', call_args)
        self.assertIn('stream', call_args)

    def test_start_logs_exception_when_worker_start_fails(self):
        """start() logs exception when worker.start() raises."""
        mock_worker = mock.MagicMock()
        mock_worker.start.side_effect = RuntimeError('start failed')
        self.runtime._WorkflowRuntime__worker = mock_worker
        with mock.patch.object(self.runtime._logger, 'exception') as mock_exception:
            with self.assertRaises(RuntimeError):
                self.runtime.start()
        mock_exception.assert_called_once()
        self.assertIn('did not start', mock_exception.call_args[0][0])

    def test_start_raises_when_worker_not_ready(self):
        listActivities.clear()
        listOrchestrators.clear()
        mock.patch(
            'dapr.ext.workflow._durabletask.worker._Registry', return_value=FakeTaskHubGrpcWorker()
        ).start()
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
        mock.patch(
            'dapr.ext.workflow._durabletask.worker._Registry', return_value=FakeTaskHubGrpcWorker()
        ).start()
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


class WorkflowRuntimeInitTest(unittest.TestCase):
    """Tests for __init__ branches: DAPR_API_TOKEN and GrpcEndpoint error."""

    def setUp(self):
        listActivities.clear()
        listOrchestrators.clear()
        mock.patch(
            'dapr.ext.workflow._durabletask.worker._Registry', return_value=FakeTaskHubGrpcWorker()
        ).start()

    def tearDown(self):
        mock.patch.stopall()

    def test_init_with_dapr_api_token(self):
        with mock.patch('dapr.ext.workflow.workflow_runtime.settings') as mock_settings:
            mock_settings.DAPR_API_TOKEN = 'test-token'
            mock_settings.DAPR_RUNTIME_HOST = '127.0.0.1'
            mock_settings.DAPR_GRPC_PORT = 50001
            runtime = WorkflowRuntime()
            self.assertIsNotNone(runtime)

    def test_init_raises_on_invalid_address(self):
        from dapr.clients import DaprInternalError

        with mock.patch(
            'dapr.ext.workflow.workflow_runtime.GrpcEndpoint',
            side_effect=ValueError('bad endpoint'),
        ):
            with self.assertRaises(DaprInternalError):
                WorkflowRuntime()


class OrchestratorWrapperTest(unittest.TestCase):
    """Tests for the orchestrationWrapper and activityWrapper inner functions."""

    def setUp(self):
        listActivities.clear()
        listOrchestrators.clear()
        self._registry_patch = mock.patch(
            'dapr.ext.workflow._durabletask.worker._Registry', return_value=FakeTaskHubGrpcWorker()
        )
        self._registry_patch.start()
        self.runtime = WorkflowRuntime()
        self.fake_registry = self.runtime._WorkflowRuntime__worker._registry

    def tearDown(self):
        mock.patch.stopall()

    def test_orchestration_wrapper_calls_workflow_without_input(self):
        called_with = {}

        def my_wf(ctx):
            called_with['ctx'] = ctx
            return 'wf_result'

        self.runtime.register_workflow(my_wf)
        wrapper_fn = self.fake_registry._orchestrator_fns['my_wf']

        mock_ctx = mock.MagicMock()
        result = wrapper_fn(mock_ctx, None)
        self.assertEqual(result, 'wf_result')
        self.assertIsNotNone(called_with.get('ctx'))

    def test_orchestration_wrapper_calls_workflow_with_input(self):
        called_with = {}

        def my_wf(ctx, inp):
            called_with['inp'] = inp
            return inp * 2

        self.runtime.register_workflow(my_wf)
        wrapper_fn = self.fake_registry._orchestrator_fns['my_wf']

        mock_ctx = mock.MagicMock()
        result = wrapper_fn(mock_ctx, 21)
        self.assertEqual(result, 42)
        self.assertEqual(called_with['inp'], 21)

    def test_orchestration_wrapper_logs_and_reraises_on_exception(self):
        def failing_wf(ctx):
            raise RuntimeError('wf boom')

        self.runtime.register_workflow(failing_wf)
        wrapper_fn = self.fake_registry._orchestrator_fns['failing_wf']

        mock_ctx = mock.MagicMock()
        mock_ctx.instance_id = 'test-instance'
        with mock.patch.object(self.runtime._logger, 'exception') as mock_exc:
            with self.assertRaises(RuntimeError):
                wrapper_fn(mock_ctx, None)
            mock_exc.assert_called_once()
            self.assertIn('test-instance', mock_exc.call_args[0][0])

    def test_activity_wrapper_calls_activity_without_input(self):
        called_with = {}

        def my_act(ctx):
            called_with['ctx'] = ctx
            return 'act_result'

        self.runtime.register_activity(my_act)
        wrapper_fn = self.fake_registry._activity_fns['my_act']

        mock_ctx = mock.MagicMock()
        result = wrapper_fn(mock_ctx, None)
        self.assertEqual(result, 'act_result')

    def test_activity_wrapper_calls_activity_with_input(self):
        def my_act(ctx, inp):
            return inp + '_done'

        self.runtime.register_activity(my_act)
        wrapper_fn = self.fake_registry._activity_fns['my_act']

        mock_ctx = mock.MagicMock()
        result = wrapper_fn(mock_ctx, 'task')
        self.assertEqual(result, 'task_done')

    def test_activity_wrapper_logs_and_reraises_on_exception(self):
        def failing_act(ctx):
            raise ValueError('act boom')

        self.runtime.register_activity(failing_act)
        wrapper_fn = self.fake_registry._activity_fns['failing_act']

        mock_ctx = mock.MagicMock()
        mock_ctx.task_id = 'task-42'
        with mock.patch.object(self.runtime._logger, 'warning') as mock_warn:
            with self.assertRaises(ValueError):
                wrapper_fn(mock_ctx, None)
            mock_warn.assert_called_once()
            self.assertIn('task-42', str(mock_warn.call_args))


class VersionedWorkflowTest(unittest.TestCase):
    """Tests for register_versioned_workflow and @versioned_workflow decorator."""

    def setUp(self):
        listActivities.clear()
        listOrchestrators.clear()
        self._registry_patch = mock.patch(
            'dapr.ext.workflow._durabletask.worker._Registry', return_value=FakeTaskHubGrpcWorker()
        )
        self._registry_patch.start()
        self.runtime = WorkflowRuntime()
        self.fake_registry = self.runtime._WorkflowRuntime__worker._registry

    def tearDown(self):
        mock.patch.stopall()

    def test_register_versioned_workflow_basic(self):
        def my_wf(ctx):
            return 'ok'

        self.runtime.register_versioned_workflow(
            my_wf, name='my_workflow', version_name='v1', is_latest=True
        )
        self.assertIn('my_workflow', listOrchestrators)
        self.assertTrue(my_wf._workflow_registered)
        self.assertEqual(my_wf._dapr_alternate_name, 'my_workflow')

    def test_register_versioned_workflow_without_version_name(self):
        def another_wf(ctx):
            return 'ok'

        self.runtime.register_versioned_workflow(
            another_wf, name='named_wf', version_name=None, is_latest=False
        )
        self.assertIn('named_wf', listOrchestrators)

    def test_register_versioned_workflow_duplicate_raises(self):
        def my_wf(ctx):
            return 'ok'

        self.runtime.register_versioned_workflow(
            my_wf, name='wf_name', version_name='v1', is_latest=True
        )
        with self.assertRaises(ValueError) as ctx:
            self.runtime.register_versioned_workflow(
                my_wf, name='wf_name', version_name='v2', is_latest=False
            )
        self.assertIn('already registered', str(ctx.exception))

    def test_register_versioned_workflow_conflicts_with_alternate_name(self):
        def my_wf(ctx):
            return 'ok'

        my_wf.__dict__['_dapr_alternate_name'] = 'existing_name'
        with self.assertRaises(ValueError) as ctx:
            self.runtime.register_versioned_workflow(
                my_wf, name='different_name', version_name='v1', is_latest=True
            )
        self.assertIn('already has an alternate name', str(ctx.exception))

    def test_versioned_workflow_orchestration_wrapper_without_input(self):
        def my_wf(ctx):
            return 'versioned_result'

        self.runtime.register_versioned_workflow(
            my_wf, name='vwf', version_name='v1', is_latest=True
        )
        wrapper_fn = self.fake_registry._orchestrator_fns['vwf']
        mock_ctx = mock.MagicMock()
        result = wrapper_fn(mock_ctx, None)
        self.assertEqual(result, 'versioned_result')

    def test_versioned_workflow_orchestration_wrapper_with_input(self):
        def my_wf(ctx, inp):
            return inp + 10

        self.runtime.register_versioned_workflow(
            my_wf, name='vwf2', version_name='v1', is_latest=True
        )
        wrapper_fn = self.fake_registry._orchestrator_fns['vwf2']
        mock_ctx = mock.MagicMock()
        result = wrapper_fn(mock_ctx, 5)
        self.assertEqual(result, 15)

    def test_versioned_workflow_decorator_with_args(self):
        @self.runtime.versioned_workflow(name='dec_vwf', version_name='v1', is_latest=True)
        def my_wf(ctx):
            return 'ok'

        self.assertIn('dec_vwf', listOrchestrators)
        self.assertEqual(my_wf._dapr_alternate_name, 'dec_vwf')

    def test_versioned_workflow_decorator_without_args(self):
        def my_wf(ctx):
            return 'ok'

        decorated = self.runtime.versioned_workflow(my_wf, name='direct_vwf', is_latest=False)
        self.assertIn('direct_vwf', listOrchestrators)
        self.assertEqual(decorated._dapr_alternate_name, 'direct_vwf')

    def test_versioned_workflow_decorator_sets_alternate_name_from_register(self):
        @self.runtime.versioned_workflow(name='vwf_name', version_name='v1', is_latest=True)
        def my_wf(ctx):
            return 'ok'

        # The decorator picks up _dapr_alternate_name set by register_versioned_workflow
        self.assertEqual(my_wf._dapr_alternate_name, 'vwf_name')


class DecoratorNoArgsTest(unittest.TestCase):
    """Tests for @workflow and @activity decorators used without parentheses."""

    def setUp(self):
        listActivities.clear()
        listOrchestrators.clear()
        mock.patch(
            'dapr.ext.workflow._durabletask.worker._Registry', return_value=FakeTaskHubGrpcWorker()
        ).start()
        self.runtime = WorkflowRuntime()

    def tearDown(self):
        mock.patch.stopall()

    def test_workflow_decorator_no_args(self):
        @self.runtime.workflow
        def my_workflow(ctx):
            return 'result'

        self.assertIn('my_workflow', listOrchestrators)
        self.assertEqual(my_workflow._dapr_alternate_name, 'my_workflow')

    def test_activity_decorator_no_args(self):
        @self.runtime.activity
        def my_activity(ctx):
            return 'result'

        self.assertIn('my_activity', listActivities)
        self.assertEqual(my_activity._dapr_alternate_name, 'my_activity')

    def test_workflow_decorator_innerfn_returns_fn(self):
        @self.runtime.workflow
        def my_workflow(ctx):
            return 'hello'

        result = my_workflow()
        self.assertIsNotNone(result)

    def test_activity_decorator_innerfn_returns_fn(self):
        @self.runtime.activity
        def my_activity(ctx):
            return 'hello'

        result = my_activity()
        self.assertIsNotNone(result)


class AlternateNameTest(unittest.TestCase):
    """Tests for the standalone alternate_name decorator."""

    def test_alternate_name_with_name(self):
        @alternate_name(name='custom')
        def my_fn(ctx):
            return 'ok'

        self.assertEqual(my_fn._dapr_alternate_name, 'custom')

    def test_alternate_name_without_name_uses_fn_name(self):
        @alternate_name()
        def my_fn(ctx):
            return 'ok'

        self.assertEqual(my_fn._dapr_alternate_name, 'my_fn')

    def test_alternate_name_innerfn_calls_through(self):
        @alternate_name(name='custom')
        def my_fn(x, y):
            return x + y

        self.assertEqual(my_fn(3, 4), 7)

    def test_alternate_name_duplicate_raises(self):
        @alternate_name(name='first')
        def my_fn(ctx):
            return 'ok'

        with self.assertRaises(ValueError) as ctx:
            alternate_name(name='second')(my_fn)
        self.assertIn('already has an alternate name', str(ctx.exception))


class PydanticInputCoercionTest(unittest.TestCase):
    """Signature-directed Pydantic input coercion in workflow/activity wrappers."""

    def setUp(self):
        listActivities.clear()
        listOrchestrators.clear()
        self._registry_patch = mock.patch(
            'dapr.ext.workflow._durabletask.worker._Registry', return_value=FakeTaskHubGrpcWorker()
        )
        self._registry_patch.start()
        self.runtime = WorkflowRuntime()
        self.fake_registry = self.runtime._WorkflowRuntime__worker._registry

    def tearDown(self):
        mock.patch.stopall()

    def test_activity_wrapper_coerces_dict_to_pydantic_model(self):
        received = {}

        def my_act(ctx, order: Order):
            received['order'] = order
            return order.amount * 2

        self.runtime.register_activity(my_act, name='pydantic_act')
        wrapper = self.fake_registry._activity_fns['pydantic_act']

        result = wrapper(mock.MagicMock(), {'order_id': 'o1', 'amount': 5.0})
        self.assertIsInstance(received['order'], Order)
        self.assertEqual(received['order'].order_id, 'o1')
        self.assertEqual(result, 10.0)

    def test_workflow_wrapper_coerces_dict_to_pydantic_model(self):
        received = {}

        def my_wf(ctx, order: Order):
            received['order'] = order
            return order.order_id

        self.runtime.register_workflow(my_wf, name='pydantic_wf')
        wrapper = self.fake_registry._orchestrator_fns['pydantic_wf']

        result = wrapper(mock.MagicMock(), {'order_id': 'o2', 'amount': 3.0})
        self.assertIsInstance(received['order'], Order)
        self.assertEqual(result, 'o2')

    def test_activity_wrapper_passthrough_when_not_annotated(self):
        def my_act(ctx, inp):
            return inp

        self.runtime.register_activity(my_act, name='plain_act')
        wrapper = self.fake_registry._activity_fns['plain_act']

        payload = {'order_id': 'o3', 'amount': 1.0}
        result = wrapper(mock.MagicMock(), payload)
        self.assertIs(result, payload)

    def test_workflow_wrapper_passthrough_for_primitive_annotation(self):
        def my_wf(ctx, n: int):
            return n + 1

        self.runtime.register_workflow(my_wf, name='int_wf')
        wrapper = self.fake_registry._orchestrator_fns['int_wf']

        result = wrapper(mock.MagicMock(), 41)
        self.assertEqual(result, 42)

    def test_activity_wrapper_handles_optional_annotation(self):
        def my_act(ctx, order: Optional[Order] = None):
            return order

        self.runtime.register_activity(my_act, name='optional_act')
        wrapper = self.fake_registry._activity_fns['optional_act']

        self.assertIsNone(wrapper(mock.MagicMock(), None))
        result = wrapper(mock.MagicMock(), {'order_id': 'o4', 'amount': 7.0})
        self.assertIsInstance(result, Order)
        self.assertEqual(result.amount, 7.0)

    def test_activity_wrapper_passes_through_existing_model_instance(self):
        instance = Order(order_id='o5', amount=9.0)

        def my_act(ctx, order: Order):
            return order

        self.runtime.register_activity(my_act, name='reuse_act')
        wrapper = self.fake_registry._activity_fns['reuse_act']

        result = wrapper(mock.MagicMock(), instance)
        self.assertIs(result, instance)

    def test_activity_wrapper_raises_validation_error_for_invalid_payload(self):
        def my_act(ctx, order: Order):
            return order

        self.runtime.register_activity(my_act, name='invalid_act')
        wrapper = self.fake_registry._activity_fns['invalid_act']

        with self.assertRaises(ValidationError):
            wrapper(mock.MagicMock(), {'order_id': 'o6'})  # missing amount

    def test_versioned_workflow_wrapper_coerces_input(self):
        received = {}

        def my_wf(ctx, order: Order):
            received['order'] = order
            return order.order_id

        self.runtime.register_versioned_workflow(
            my_wf, name='versioned_pydantic', version_name='v1', is_latest=True
        )
        wrapper = self.fake_registry._orchestrator_fns['versioned_pydantic']

        result = wrapper(mock.MagicMock(), {'order_id': 'v1', 'amount': 2.0})
        self.assertIsInstance(received['order'], Order)
        self.assertEqual(result, 'v1')

    def test_activity_wrapper_passes_none_to_fn_that_expects_input(self):
        """Regression: Optional[Model] without a default must receive None, not be dropped."""

        def my_act(ctx, order: Optional[Order]):
            return order

        self.runtime.register_activity(my_act, name='optional_no_default_act')
        wrapper = self.fake_registry._activity_fns['optional_no_default_act']

        self.assertIsNone(wrapper(mock.MagicMock(), None))
        wrapper = self.fake_registry._activity_fns['optional_no_default_act']

        self.assertIsNone(wrapper(mock.MagicMock(), None))
        wrapper = self.fake_registry._activity_fns['optional_no_default_act']

        self.assertIsNone(wrapper(mock.MagicMock(), None))
