import unittest
from unittest.mock import MagicMock

from google.protobuf.struct_pb2 import Struct

from dapr.aio.clients.grpc.subscription import Subscription as SubscriptionAsync
from dapr.clients.grpc.subscription import StreamInactiveError, Subscription, SubscriptionMessage
from dapr.proto.runtime.v1.appcallback_pb2 import TopicEventRequest


class SubscriptionMessageTests(unittest.TestCase):
    def test_subscription_message_init_raw_text(self):
        extensions = Struct()
        extensions['field1'] = 'value1'
        extensions['field2'] = 42
        extensions['field3'] = True

        msg = TopicEventRequest(
            id='id',
            data=b'hello',
            data_content_type='text/plain',
            topic='topicA',
            pubsub_name='pubsub_name',
            source='source',
            type='type',
            spec_version='spec_version',
            path='path',
            extensions=extensions,
        )
        subscription_message = SubscriptionMessage(msg=msg)

        self.assertEqual('id', subscription_message.id())
        self.assertEqual('source', subscription_message.source())
        self.assertEqual('type', subscription_message.type())
        self.assertEqual('spec_version', subscription_message.spec_version())
        self.assertEqual('text/plain', subscription_message.data_content_type())
        self.assertEqual('topicA', subscription_message.topic())
        self.assertEqual('pubsub_name', subscription_message.pubsub_name())
        self.assertEqual(b'hello', subscription_message.raw_data())
        self.assertEqual('hello', subscription_message.data())
        self.assertEqual(
            {'field1': 'value1', 'field2': 42, 'field3': True}, subscription_message.extensions()
        )

    def test_subscription_message_init_raw_text_non_utf(self):
        msg = TopicEventRequest(
            id='id',
            data=b'\x80\x81\x82',
            data_content_type='text/plain',
            topic='topicA',
            pubsub_name='pubsub_name',
            source='source',
            type='type',
            spec_version='spec_version',
            path='path',
        )
        subscription_message = SubscriptionMessage(msg=msg)

        self.assertEqual(b'\x80\x81\x82', subscription_message.raw_data())
        self.assertIsNone(subscription_message.data())

    def test_subscription_message_init_json(self):
        msg = TopicEventRequest(
            id='id',
            data=b'{"a": 1}',
            data_content_type='application/json',
            topic='topicA',
            pubsub_name='pubsub_name',
            source='source',
            type='type',
            spec_version='spec_version',
            path='path',
        )
        subscription_message = SubscriptionMessage(msg=msg)

        self.assertEqual(b'{"a": 1}', subscription_message.raw_data())
        self.assertEqual({'a': 1}, subscription_message.data())
        print(subscription_message.data()['a'])

    def test_subscription_message_init_json_faimly(self):
        msg = TopicEventRequest(
            id='id',
            data=b'{"a": 1}',
            data_content_type='application/vnd.api+json',
            topic='topicA',
            pubsub_name='pubsub_name',
            source='source',
            type='type',
            spec_version='spec_version',
            path='path',
        )
        subscription_message = SubscriptionMessage(msg=msg)

        self.assertEqual(b'{"a": 1}', subscription_message.raw_data())
        self.assertEqual({'a': 1}, subscription_message.data())

    def test_subscription_message_init_unknown_content_type(self):
        msg = TopicEventRequest(
            id='id',
            data=b'{"a": 1}',
            data_content_type='unknown/content-type',
            topic='topicA',
            pubsub_name='pubsub_name',
            source='source',
            type='type',
            spec_version='spec_version',
            path='path',
        )
        subscription_message = SubscriptionMessage(msg=msg)

        self.assertEqual(b'{"a": 1}', subscription_message.raw_data())
        self.assertIsNone(subscription_message.data())


class _StreamClosedDuringInitialRead:
    def __init__(self, subscription: Subscription):
        self._subscription = subscription

    def __next__(self):
        self._subscription.close()
        raise RuntimeError('stream cancelled')

    def cancel(self):
        pass


class SubscriptionCloseTests(unittest.TestCase):
    def test_start_after_close_raises_stream_inactive(self):
        subscription = Subscription(MagicMock(), 'pubsub', 'topic')
        subscription.close()

        with self.assertRaises(StreamInactiveError):
            subscription.start()

    def test_close_during_initial_read_raises_stream_inactive(self):
        stub = MagicMock()
        subscription = Subscription(stub, 'pubsub', 'topic')
        stub.SubscribeTopicEventsAlpha1.return_value = _StreamClosedDuringInitialRead(subscription)

        with self.assertRaises(StreamInactiveError):
            subscription.start()


class SubscriptionAsyncCloseTests(unittest.IsolatedAsyncioTestCase):
    async def test_start_after_close_raises_stream_inactive(self):
        subscription = SubscriptionAsync(MagicMock(), 'pubsub', 'topic')
        await subscription.close()

        with self.assertRaises(StreamInactiveError):
            await subscription.start()
