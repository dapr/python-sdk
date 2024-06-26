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

from unittest.mock import MagicMock, Mock

from dapr.clients.grpc._request import InvokeMethodRequest
from dapr.clients.grpc._response import InvokeMethodResponse, TopicEventResponse
from dapr.ext.grpc._servicer import _CallbackServicer
from dapr.proto import common_v1, appcallback_v1

from google.protobuf.any_pb2 import Any as GrpcAny


class OnInvokeTests(unittest.TestCase):
    def setUp(self):
        self._servicer = _CallbackServicer()

    def _on_invoke(self, method_name, method_cb):
        self._servicer.register_method(method_name, method_cb)

        # fake context
        fake_context = MagicMock()
        fake_context.invocation_metadata.return_value = (
            ('key1', 'value1'),
            ('key2', 'value1'),
        )

        return self._servicer.OnInvoke(
            common_v1.InvokeRequest(method=method_name, data=GrpcAny()),
            fake_context,
        )

    def test_on_invoke_return_str(self):
        def method_cb(request: InvokeMethodRequest):
            return 'method_str_cb'

        resp = self._on_invoke('method_str', method_cb)

        self.assertEqual(b'method_str_cb', resp.data.value)

    def test_on_invoke_return_bytes(self):
        def method_cb(request: InvokeMethodRequest):
            return b'method_str_cb'

        resp = self._on_invoke('method_bytes', method_cb)

        self.assertEqual(b'method_str_cb', resp.data.value)

    def test_on_invoke_return_proto(self):
        def method_cb(request: InvokeMethodRequest):
            return common_v1.StateItem(key='fake_key')

        resp = self._on_invoke('method_proto', method_cb)

        state = common_v1.StateItem()
        resp.data.Unpack(state)

        self.assertEqual('fake_key', state.key)

    def test_on_invoke_return_invoke_method_response(self):
        def method_cb(request: InvokeMethodRequest):
            return InvokeMethodResponse(
                data='fake_data',
                content_type='text/plain',
            )

        resp = self._on_invoke('method_resp', method_cb)

        self.assertEqual(b'fake_data', resp.data.value)
        self.assertEqual('text/plain', resp.content_type)

    def test_on_invoke_invalid_response(self):
        def method_cb(request: InvokeMethodRequest):
            return 1000

        with self.assertRaises(NotImplementedError):
            self._on_invoke('method_resp', method_cb)


class TopicSubscriptionTests(unittest.TestCase):
    def setUp(self):
        self._servicer = _CallbackServicer()
        self._topic1_method = Mock()
        self._topic2_method = Mock()
        self._topic3_method = Mock()
        self._topic3_method.return_value = TopicEventResponse('success')
        self._topic4_method = Mock()

        self._servicer.register_topic('pubsub1', 'topic1', self._topic1_method, {'session': 'key'})
        self._servicer.register_topic('pubsub1', 'topic3', self._topic3_method, {'session': 'key'})
        self._servicer.register_topic('pubsub2', 'topic2', self._topic2_method, {'session': 'key'})
        self._servicer.register_topic('pubsub2', 'topic3', self._topic3_method, {'session': 'key'})
        self._servicer.register_topic(
            'pubsub3',
            'topic4',
            self._topic4_method,
            {'session': 'key'},
            disable_topic_validation=True,
        )

        # fake context
        self.fake_context = MagicMock()
        self.fake_context.invocation_metadata.return_value = (
            ('key1', 'value1'),
            ('key2', 'value1'),
        )

    def test_duplicated_topic(self):
        with self.assertRaises(ValueError):
            self._servicer.register_topic(
                'pubsub1', 'topic1', self._topic1_method, {'session': 'key'}
            )

    def test_list_topic_subscription(self):
        resp = self._servicer.ListTopicSubscriptions(None, None)
        self.assertEqual('pubsub1', resp.subscriptions[0].pubsub_name)
        self.assertEqual('topic1', resp.subscriptions[0].topic)
        self.assertEqual({'session': 'key'}, resp.subscriptions[0].metadata)
        self.assertEqual('pubsub1', resp.subscriptions[1].pubsub_name)
        self.assertEqual('topic3', resp.subscriptions[1].topic)
        self.assertEqual({'session': 'key'}, resp.subscriptions[1].metadata)
        self.assertEqual('pubsub2', resp.subscriptions[2].pubsub_name)
        self.assertEqual('topic2', resp.subscriptions[2].topic)
        self.assertEqual({'session': 'key'}, resp.subscriptions[2].metadata)
        self.assertEqual('pubsub2', resp.subscriptions[3].pubsub_name)
        self.assertEqual('topic3', resp.subscriptions[3].topic)
        self.assertEqual({'session': 'key'}, resp.subscriptions[3].metadata)
        self.assertEqual('topic4', resp.subscriptions[4].topic)
        self.assertEqual({'session': 'key'}, resp.subscriptions[4].metadata)

    def test_topic_event(self):
        self._servicer.OnTopicEvent(
            appcallback_v1.TopicEventRequest(pubsub_name='pubsub1', topic='topic1'),
            self.fake_context,
        )

        self._topic1_method.assert_called_once()

    def test_topic3_event_called_once(self):
        self._servicer.OnTopicEvent(
            appcallback_v1.TopicEventRequest(pubsub_name='pubsub1', topic='topic3'),
            self.fake_context,
        )

        self._topic3_method.assert_called_once()

    def test_topic3_event_response(self):
        response = self._servicer.OnTopicEvent(
            appcallback_v1.TopicEventRequest(pubsub_name='pubsub1', topic='topic3'),
            self.fake_context,
        )
        self.assertIsInstance(response, appcallback_v1.TopicEventResponse)
        self.assertEqual(
            response.status, appcallback_v1.TopicEventResponse.TopicEventResponseStatus.SUCCESS
        )

    def test_disable_topic_validation(self):
        self._servicer.OnTopicEvent(
            appcallback_v1.TopicEventRequest(pubsub_name='pubsub3', topic='should_be_ignored'),
            self.fake_context,
        )

        self._topic4_method.assert_called_once()

    def test_non_registered_topic(self):
        with self.assertRaises(NotImplementedError):
            self._servicer.OnTopicEvent(
                appcallback_v1.TopicEventRequest(pubsub_name='pubsub1', topic='topic_non_existed'),
                self.fake_context,
            )


class BindingTests(unittest.TestCase):
    def setUp(self):
        self._servicer = _CallbackServicer()
        self._binding1_method = Mock()
        self._binding2_method = Mock()

        self._servicer.register_binding('binding1', self._binding1_method)
        self._servicer.register_binding('binding2', self._binding2_method)

        # fake context
        self.fake_context = MagicMock()
        self.fake_context.invocation_metadata.return_value = (
            ('key1', 'value1'),
            ('key2', 'value1'),
        )

    def test_duplicated_binding(self):
        with self.assertRaises(ValueError):
            self._servicer.register_binding('binding1', self._binding1_method)

    def test_list_bindings(self):
        resp = self._servicer.ListInputBindings(None, None)
        self.assertEqual('binding1', resp.bindings[0])
        self.assertEqual('binding2', resp.bindings[1])

    def test_binding_event(self):
        self._servicer.OnBindingEvent(
            appcallback_v1.BindingEventRequest(name='binding1'),
            self.fake_context,
        )

        self._binding1_method.assert_called_once()

    def test_non_registered_binding(self):
        with self.assertRaises(NotImplementedError):
            self._servicer.OnBindingEvent(
                appcallback_v1.BindingEventRequest(name='binding3'),
                self.fake_context,
            )


if __name__ == '__main__':
    unittest.main()
