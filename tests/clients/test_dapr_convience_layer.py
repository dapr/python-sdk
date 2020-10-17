# -*- coding: utf-8 -*-

"""
Copyright (c) Microsoft Corporation.
Licensed under the MIT License.
"""

import unittest

from unittest.mock import MagicMock, patch
from dapr.clients import DaprClient
from dapr.clients.grpc._response import DaprResponse
from dapr.proto import api_v1


class PublisherTests(unittest.TestCase):
    @patch('grpc.insecure_channel')
    def setUp(self, insecure_channel_mock):
        self.client = DaprClient()
        self.client._stub = MagicMock()
        self.with_call_mock = self.client._stub.PublishEvent.with_call
        self.with_call_mock.return_value = (None, MagicMock())

    def test_publish_event_string_data(self):
        resp = self.client.publish_event(
            pubsub_name='pubsub',
            topic='TOPIC_A',
            data='foo',
        )

        self.assertIsInstance(resp, DaprResponse)

        self.with_call_mock.assert_called_with(api_v1.PublishEventRequest(
            pubsub_name='pubsub',
            topic='TOPIC_A',
            data=bytes('foo', 'utf-8')), metadata=()
        )

    def test_publish_event_bytes_data(self):
        resp = self.client.publish_event(
            pubsub_name='pubsub',
            topic='TOPIC_A',
            data=bytes('foo', 'utf-8'),
        )

        self.assertIsInstance(resp, DaprResponse)

        self.with_call_mock.assert_called_with(api_v1.PublishEventRequest(
            pubsub_name='pubsub',
            topic='TOPIC_A',
            data=bytes('foo', 'utf-8')), metadata=()
        )

    def test_publish_event_raises_value_error_for_wrong_data_type(self):
        self.assertRaises(ValueError,
                          self.client.publish_event, pubsub_name='pubsub', topic='TOPIC_A', data=1)
        self.assertRaises(ValueError,
                          self.client.publish_event, pubsub_name='pubsub', topic='TOPIC_A', data={})
        self.assertRaises(ValueError,
                          self.client.publish_event, pubsub_name='pubsub', topic='TOPIC_A', data=[])


if __name__ == '__main__':
    unittest.main()
