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
import warnings
from unittest.mock import MagicMock, patch

from dapr.conf import settings
from dapr.ext.grpc import App, BindingRequest, InvokeMethodRequest, Rule, SubscriptionMessage
from dapr.proto import appcallback_v1


class AppTests(unittest.TestCase):
    def setUp(self):
        self._app = App()

    def test_method_decorator(self):
        @self._app.method('Method1')
        def method1(request: InvokeMethodRequest):
            pass

        @self._app.method('Method2')
        def method2(request: InvokeMethodRequest):
            pass

        method_map = self._app._servicer._invoke_method_map
        self.assertIn('AppTests.test_method_decorator.<locals>.method1', str(method_map['Method1']))
        self.assertIn('AppTests.test_method_decorator.<locals>.method2', str(method_map['Method2']))

    def test_binding_decorator(self):
        @self._app.binding('binding1')
        def binding1(request: BindingRequest):
            pass

        binding_map = self._app._servicer._binding_map
        self.assertIn(
            'AppTests.test_binding_decorator.<locals>.binding1', str(binding_map['binding1'])
        )

    def test_subscribe_decorator(self):
        @self._app.subscribe(pubsub_name='pubsub', topic='topic')
        def handle_default(event: SubscriptionMessage) -> None:
            pass

        @self._app.subscribe(
            pubsub_name='pubsub', topic='topic', rule=Rule('event.type == "test"', 1)
        )
        def handle_test_event(event: SubscriptionMessage) -> None:
            pass

        @self._app.subscribe(pubsub_name='pubsub', topic='topic2', dead_letter_topic='topic2_dead')
        def handle_dead_letter(event: SubscriptionMessage) -> None:
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

    def test_register_health_check(self):
        def health_check_cb():
            pass

        self._app.register_health_check(health_check_cb)
        registered_cb = self._app._health_check_servicer._health_check_cb
        self.assertIn(
            'AppTests.test_register_health_check.<locals>.health_check_cb', str(registered_cb)
        )

    def test_no_health_check(self):
        registered_cb = self._app._health_check_servicer._health_check_cb
        self.assertIsNone(registered_cb)


class SubscribeEventTypeInferenceTests(unittest.TestCase):
    """subscribe() infers the delivered event type from the handler's annotation."""

    def setUp(self):
        self._app = App()
        self.fake_context = MagicMock()
        self.fake_context.invocation_metadata.return_value = ()

    def _subscribe_and_deliver(self, handler):
        received = []
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter('always')
            wrapped = self._app.subscribe(pubsub_name='pubsub', topic='topic')(handler)
            del wrapped

        def recording_handler(event):
            received.append(event)
            return handler(event)

        self._app._servicer._topic_map['pubsub:topic:'] = recording_handler
        request = appcallback_v1.TopicEventRequest(
            id='event-1',
            data_content_type='application/json',
            data=b'{"a": 1}',
            topic='topic',
            pubsub_name='pubsub',
        )
        self._app._servicer.OnTopicEvent(request, self.fake_context)
        deprecations = [w for w in caught if issubclass(w.category, DeprecationWarning)]
        return received[0], deprecations

    def test_unannotated_handler_warns_and_gets_legacy_event(self):
        def handler(event):
            pass

        event, deprecations = self._subscribe_and_deliver(handler)
        self.assertNotIsInstance(event, SubscriptionMessage)
        self.assertEqual('event-1', event.EventID())
        self.assertEqual(1, len(deprecations))
        self.assertIn('SubscriptionMessage', str(deprecations[0].message))

    def test_annotated_handler_gets_subscription_message_without_warning(self):
        def handler(event: SubscriptionMessage):
            pass

        event, deprecations = self._subscribe_and_deliver(handler)
        self.assertIsInstance(event, SubscriptionMessage)
        self.assertEqual('event-1', event.id())
        self.assertEqual([], deprecations)

    def test_legacy_annotated_handler_warns_and_gets_legacy_event(self):
        from cloudevents.sdk.event import v1

        def handler(event: v1.Event):
            pass

        event, deprecations = self._subscribe_and_deliver(handler)
        self.assertIsInstance(event, v1.Event)
        self.assertEqual(1, len(deprecations))

    def test_string_annotation_resolves(self):
        def handler(event: 'SubscriptionMessage'):
            pass

        event, deprecations = self._subscribe_and_deliver(handler)
        self.assertIsInstance(event, SubscriptionMessage)
        self.assertEqual([], deprecations)

    def test_unresolvable_annotation_falls_back_to_legacy(self):
        def handler(event):
            pass

        handler.__annotations__ = {'event': 'NotARealType'}
        event, deprecations = self._subscribe_and_deliver(handler)
        self.assertNotIsInstance(event, SubscriptionMessage)
        self.assertEqual(1, len(deprecations))


class AppGrpcOptionsTests(unittest.TestCase):
    """Exercises options passed to grpc.server() based on env var / constructor arg."""

    @patch.object(settings, 'DAPR_GRPC_MAX_INBOUND_MESSAGE_SIZE_BYTES', 0)
    @patch('dapr.ext.grpc.app.grpc.server')
    def test_default_no_size_options(self, mock_server):
        mock_server.return_value = MagicMock()

        App()

        _, kwargs = mock_server.call_args
        options = dict(kwargs.get('options') or [])
        self.assertNotIn('grpc.max_send_message_length', options)
        self.assertNotIn('grpc.max_receive_message_length', options)

    @patch.object(settings, 'DAPR_GRPC_MAX_INBOUND_MESSAGE_SIZE_BYTES', 8 * 1024 * 1024)
    @patch('dapr.ext.grpc.app.grpc.server')
    def test_env_var_sets_receive_only(self, mock_server):
        mock_server.return_value = MagicMock()

        App()

        _, kwargs = mock_server.call_args
        options = dict(kwargs.get('options') or [])
        self.assertEqual(options.get('grpc.max_receive_message_length'), 8 * 1024 * 1024)
        self.assertNotIn('grpc.max_send_message_length', options)

    @patch.object(settings, 'DAPR_GRPC_MAX_INBOUND_MESSAGE_SIZE_BYTES', 8 * 1024 * 1024)
    @patch('dapr.ext.grpc.app.grpc.server')
    def test_constructor_arg_overrides_env(self, mock_server):
        mock_server.return_value = MagicMock()

        App(max_grpc_message_length=32 * 1024 * 1024)

        _, kwargs = mock_server.call_args
        options = dict(kwargs.get('options') or [])
        self.assertEqual(options.get('grpc.max_send_message_length'), 32 * 1024 * 1024)
        self.assertEqual(options.get('grpc.max_receive_message_length'), 32 * 1024 * 1024)


if __name__ == '__main__':
    unittest.main()
