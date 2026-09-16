# -*- coding: utf-8 -*-

"""
Copyright 2025 The Dapr Authors
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

import asyncio
import unittest
import warnings
from unittest.mock import MagicMock, patch

from dapr.conf import settings
from dapr.ext.grpc.aio import (
    App,
    BindingRequest,
    InvokeMethodRequest,
    JobEvent,
    Rule,
    SubscriptionMessage,
)


class AppTests(unittest.TestCase):
    def setUp(self):
        self._app = App()

    def test_method_decorator(self):
        @self._app.method('Method1')
        async def method1(request: InvokeMethodRequest):
            pass

        @self._app.method('Method2')
        async def method2(request: InvokeMethodRequest):
            pass

        method_map = self._app._servicer._invoke_method_map
        self.assertIn('AppTests.test_method_decorator.<locals>.method1', str(method_map['Method1']))
        self.assertIn('AppTests.test_method_decorator.<locals>.method2', str(method_map['Method2']))

    def test_binding_decorator(self):
        @self._app.binding('binding1')
        async def binding1(request: BindingRequest):
            pass

        binding_map = self._app._servicer._binding_map
        self.assertIn(
            'AppTests.test_binding_decorator.<locals>.binding1', str(binding_map['binding1'])
        )

    def test_subscribe_decorator(self):
        @self._app.subscribe(pubsub_name='pubsub', topic='topic')
        async def handle_default(event: SubscriptionMessage) -> None:
            pass

        @self._app.subscribe(
            pubsub_name='pubsub', topic='topic', rule=Rule('event.type == "test"', 1)
        )
        async def handle_test_event(event: SubscriptionMessage) -> None:
            pass

        @self._app.subscribe(pubsub_name='pubsub', topic='topic2', dead_letter_topic='topic2_dead')
        async def handle_dead_letter(event: SubscriptionMessage) -> None:
            pass

        subscription_map = self._app._servicer._topic_map
        self.assertIn(
            'AppTests.test_subscribe_decorator.<locals>.handle_default',
            str(subscription_map['pubsub:topic:']),
        )
        self.assertIn(
            'AppTests.test_subscribe_decorator.<locals>.handle_test_event',
            str(subscription_map['pubsub:topic:handle_test_event']),
        )
        self.assertIn(
            'AppTests.test_subscribe_decorator.<locals>.handle_dead_letter',
            str(subscription_map['pubsub:topic2:']),
        )

    def test_job_event_decorator(self):
        @self._app.job_event('job1')
        async def handle_job(event: JobEvent) -> None:
            pass

        job_map = self._app._servicer._job_event_map
        self.assertIn('AppTests.test_job_event_decorator.<locals>.handle_job', str(job_map['job1']))

    def test_decorators_return_the_handler(self):
        """Unlike the sync App, the aio decorators leave the decorated name bound."""

        @self._app.method('Method1')
        async def method1(request: InvokeMethodRequest):
            pass

        @self._app.binding('binding1')
        async def binding1(request: BindingRequest):
            pass

        @self._app.subscribe(pubsub_name='pubsub', topic='topic')
        async def handle_event(event: SubscriptionMessage) -> None:
            pass

        @self._app.job_event('job1')
        async def handle_job(event: JobEvent) -> None:
            pass

        for handler in (method1, binding1, handle_event, handle_job):
            self.assertTrue(callable(handler))

    def test_subscribe_warns_for_unannotated_handler(self):
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter('always')

            @self._app.subscribe(pubsub_name='pubsub', topic='topic')
            async def handler(event):
                pass

        deprecations = [w for w in caught if issubclass(w.category, DeprecationWarning)]
        self.assertEqual(1, len(deprecations))
        self.assertIn('SubscriptionMessage', str(deprecations[0].message))

    def test_subscribe_annotated_handler_does_not_warn(self):
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter('always')

            @self._app.subscribe(pubsub_name='pubsub', topic='topic')
            async def handler(event: SubscriptionMessage):
                pass

        deprecations = [w for w in caught if issubclass(w.category, DeprecationWarning)]
        self.assertEqual([], deprecations)

    def test_register_health_check(self):
        async def health_check_cb():
            pass

        self._app.register_health_check(health_check_cb)
        registered_cb = self._app._health_check_servicer._health_check_cb
        self.assertIn(
            'AppTests.test_register_health_check.<locals>.health_check_cb', str(registered_cb)
        )

    def test_no_health_check(self):
        registered_cb = self._app._health_check_servicer._health_check_cb
        self.assertIsNone(registered_cb)


class AppServerCreationTests(unittest.TestCase):
    """The aio server is built lazily so it binds to the loop that will serve requests."""

    def test_server_is_not_created_on_init(self):
        app = App()

        self.assertIsNone(app._server)

    @patch('dapr.ext.grpc.aio.app.grpc.aio.server')
    def test_create_server_registers_every_servicer(self, mock_server):
        mock_server.return_value = MagicMock()
        app = App()

        server = app._create_server()

        registered_services = {
            handler.service_name()
            for call in server.add_generic_rpc_handlers.call_args_list
            for handler in call[0][0]
        }
        self.assertEqual(
            {
                'dapr.proto.runtime.v1.AppCallback',
                'dapr.proto.runtime.v1.AppCallbackAlpha',
                'dapr.proto.runtime.v1.AppCallbackHealthCheck',
            },
            registered_services,
        )
        self.assertIs(mock_server.return_value, server)

    @patch('dapr.ext.grpc.aio.app.grpc.aio.server')
    def test_create_server_passes_kwargs_through(self, mock_server):
        mock_server.return_value = MagicMock()
        app = App(max_grpc_message_length=32 * 1024 * 1024)

        app._create_server()

        _, kwargs = mock_server.call_args
        options = dict(kwargs.get('options') or [])
        self.assertEqual(32 * 1024 * 1024, options.get('grpc.max_send_message_length'))
        self.assertEqual(32 * 1024 * 1024, options.get('grpc.max_receive_message_length'))


class AppGrpcOptionsTests(unittest.TestCase):
    """Exercises options passed to grpc.aio.server() based on env var / constructor arg."""

    def _options(self, app):
        return dict(app._server_kwargs.get('options') or [])

    @patch.object(settings, 'DAPR_GRPC_MAX_INBOUND_MESSAGE_SIZE_BYTES', 0)
    def test_default_no_size_options(self):
        options = self._options(App())

        self.assertNotIn('grpc.max_send_message_length', options)
        self.assertNotIn('grpc.max_receive_message_length', options)

    @patch.object(settings, 'DAPR_GRPC_MAX_INBOUND_MESSAGE_SIZE_BYTES', 8 * 1024 * 1024)
    def test_env_var_sets_receive_only(self):
        options = self._options(App())

        self.assertEqual(8 * 1024 * 1024, options.get('grpc.max_receive_message_length'))
        self.assertNotIn('grpc.max_send_message_length', options)

    @patch.object(settings, 'DAPR_GRPC_MAX_INBOUND_MESSAGE_SIZE_BYTES', 8 * 1024 * 1024)
    def test_constructor_arg_overrides_env(self):
        options = self._options(App(max_grpc_message_length=32 * 1024 * 1024))

        self.assertEqual(32 * 1024 * 1024, options.get('grpc.max_send_message_length'))
        self.assertEqual(32 * 1024 * 1024, options.get('grpc.max_receive_message_length'))

    def test_explicit_kwargs_replace_options(self):
        app = App(migration_thread_pool=None, maximum_concurrent_rpcs=7)

        self.assertEqual(7, app._server_kwargs['maximum_concurrent_rpcs'])
        self.assertNotIn('options', app._server_kwargs)


class AppExternalServiceTests(unittest.TestCase):
    @patch('dapr.ext.grpc.aio.app.grpc.aio.server')
    def test_external_service_is_registered_when_server_is_created(self, mock_server):
        mock_server.return_value = MagicMock()
        app = App()
        servicer_callback = MagicMock()
        external_servicer = MagicMock()

        app.add_external_service(servicer_callback, external_servicer)
        servicer_callback.assert_not_called()

        server = app._create_server()

        servicer_callback.assert_called_once_with(external_servicer, server)

    @patch('dapr.ext.grpc.aio.app.grpc.aio.server')
    def test_external_service_after_start_raises(self, mock_server):
        """A running grpc.aio server cannot take new services, so late registration raises."""
        mock_server.return_value = MagicMock()
        app = App()
        app._server = mock_server.return_value  # simulate a started app

        with self.assertRaises(RuntimeError) as exception_context:
            app.add_external_service(MagicMock(), MagicMock())

        self.assertIn('before the app is started', str(exception_context.exception))


async def _suspending_start() -> None:
    """Stands in for grpc.aio's start(), yielding so concurrent callers really interleave."""
    await asyncio.sleep(0.05)


class AppLifecycleTests(unittest.IsolatedAsyncioTestCase):
    async def test_stop_before_start_is_a_noop(self):
        app = App()

        await app.stop()

        self.assertIsNone(app._server)

    @patch('dapr.ext.grpc.aio.app.grpc.aio.server')
    async def test_double_start_raises(self, mock_server):
        mock_server.return_value = MagicMock()
        mock_server.return_value.start = unittest.mock.AsyncMock()
        app = App()

        await app.start(app_port=50055, listen_address='127.0.0.1')

        with self.assertRaises(RuntimeError):
            await app.start(app_port=50055, listen_address='127.0.0.1')

    @patch('dapr.ext.grpc.aio.app.grpc.aio.server')
    async def test_concurrent_starts_raise(self, mock_server):
        """Only one of two concurrent start() calls may win.

        The mocked start() suspends, so the two calls genuinely interleave — without that the
        first would run to completion before the second began and the race would go untested.
        """
        mock_server.return_value = MagicMock()
        mock_server.return_value.start = unittest.mock.AsyncMock(side_effect=_suspending_start)
        app = App()

        results = await asyncio.gather(
            app.start(app_port=50055, listen_address='127.0.0.1'),
            app.start(app_port=50056, listen_address='127.0.0.1'),
            return_exceptions=True,
        )

        errors = [r for r in results if isinstance(r, RuntimeError)]
        self.assertEqual(1, len(errors), f'expected exactly one rejection, got {results}')
        self.assertEqual(1, mock_server.call_count, 'a second server must not be built')

    @patch('dapr.ext.grpc.aio.app.grpc.aio.server')
    async def test_external_service_during_start_raises(self, mock_server):
        """Registration is rejected while a start() is still in flight, not just after it."""
        mock_server.return_value = MagicMock()
        mock_server.return_value.start = unittest.mock.AsyncMock(side_effect=_suspending_start)
        app = App()

        start_task = asyncio.ensure_future(app.start(app_port=50055, listen_address='127.0.0.1'))
        await asyncio.sleep(0)  # let start() reach its await with the slot claimed

        with self.assertRaises(RuntimeError):
            app.add_external_service(MagicMock(), MagicMock())

        await start_task

    @patch('dapr.ext.grpc.aio.app.grpc.aio.server')
    async def test_stop_clears_the_server_so_the_app_can_restart(self, mock_server):
        mock_server.return_value = MagicMock()
        mock_server.return_value.start = unittest.mock.AsyncMock()
        mock_server.return_value.stop = unittest.mock.AsyncMock()
        app = App()

        await app.start(app_port=50055, listen_address='127.0.0.1')
        await app.stop(grace=0)

        self.assertIsNone(app._server)
        mock_server.return_value.stop.assert_awaited_once_with(0)


class AppLoopGuardTests(unittest.IsolatedAsyncioTestCase):
    """The lifecycle lock binds to a loop, so loop identity is part of the contract."""

    async def test_foreign_loop_with_a_live_server_raises(self):
        app = App()
        app._server = MagicMock()
        app._lifecycle_lock = asyncio.Lock()
        app._lifecycle_loop = asyncio.new_event_loop()
        self.addCleanup(app._lifecycle_loop.close)

        with self.assertRaises(RuntimeError) as exception_context:
            app._lock_for_running_loop()

        self.assertIn('different event loop', str(exception_context.exception))

    def _app_with_a_dead_owning_loop(self) -> App:
        dead_loop = asyncio.new_event_loop()
        dead_loop.close()
        app = App()
        app._server = MagicMock()
        app._lifecycle_lock = asyncio.Lock()
        app._lifecycle_loop = dead_loop
        return app

    async def test_stop_abandons_a_server_whose_loop_is_closed(self):
        """stop() is the documented remedy, so it must not be refused - but it must warn.

        The server cannot actually be shut down without its loop, and its listener survives.
        """
        app = self._app_with_a_dead_owning_loop()

        with self.assertLogs('dapr.ext.grpc.aio.app', level='WARNING') as logs:
            await app.stop(grace=0)

        self.assertIsNone(app._server, 'the unreachable server must be released')
        self.assertIn('second server', '\n'.join(logs.output))

    async def test_start_refuses_while_an_unreachable_server_is_still_bound(self):
        """Rebinding would quietly add a second listener, since grpc enables SO_REUSEPORT."""
        app = self._app_with_a_dead_owning_loop()

        with self.assertRaises(RuntimeError) as exception_context:
            await app.start(app_port=50055, listen_address='127.0.0.1')

        self.assertIn('different event loop', str(exception_context.exception))


if __name__ == '__main__':
    unittest.main()
