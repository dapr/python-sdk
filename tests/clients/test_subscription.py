import asyncio
import queue
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from google.protobuf.struct_pb2 import Struct
from grpc import StatusCode
from grpc.aio import AioRpcError

from dapr.aio.clients.grpc import subscription as subscription_async_module
from dapr.aio.clients.grpc.subscription import Subscription as SubscriptionAsync
from dapr.clients.grpc import subscription as subscription_module
from dapr.clients.grpc.subscription import StreamInactiveError, Subscription, SubscriptionMessage
from dapr.proto import api_v1
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


class _StreamClosedDuringInitialReadAsync:
    def __init__(self, subscription: SubscriptionAsync, error: BaseException, close: bool = True):
        self._subscription = subscription
        self._error = error
        self._close = close

    async def read(self):
        if self._close:
            await self._subscription.close()
        raise self._error

    def cancel(self):
        pass


class SubscriptionAsyncInitialReadTests(unittest.IsolatedAsyncioTestCase):
    async def test_close_during_initial_read_raises_stream_inactive(self):
        errors = (AioRpcError(StatusCode.CANCELLED), asyncio.CancelledError())
        for error in errors:
            with self.subTest(error=type(error).__name__):
                stub = MagicMock()
                subscription = SubscriptionAsync(stub, 'pubsub', 'topic')
                stream = _StreamClosedDuringInitialReadAsync(subscription, error)
                stub.SubscribeTopicEventsAlpha1.return_value = stream

                with self.assertRaises(StreamInactiveError):
                    await subscription.start()

    async def test_cancellation_during_initial_read_propagates_while_open(self):
        stub = MagicMock()
        subscription = SubscriptionAsync(stub, 'pubsub', 'topic')
        error = asyncio.CancelledError()
        stream = _StreamClosedDuringInitialReadAsync(subscription, error, close=False)
        stub.SubscribeTopicEventsAlpha1.return_value = stream

        with self.assertRaises(asyncio.CancelledError):
            await subscription.start()


def _topic_stream_responses(event_id: str) -> list:
    initial_response = api_v1.SubscribeTopicEventsResponseAlpha1(
        initial_response=api_v1.SubscribeTopicEventsResponseInitialAlpha1()
    )
    event = TopicEventRequest(id=event_id)
    event_response = api_v1.SubscribeTopicEventsResponseAlpha1(event_message=event)
    return [initial_response, event_response]


class _FakeTopicStream:
    def __init__(self, event_id: str):
        self._responses = iter(_topic_stream_responses(event_id))

    def __next__(self):
        return next(self._responses)

    def cancel(self):
        pass


class _FakeTopicStreamAsync:
    def __init__(self, event_id: str):
        self._responses = iter(_topic_stream_responses(event_id))

    async def read(self):
        return next(self._responses)

    def cancel(self):
        pass


def _drain_acked_ids(send_queue) -> list:
    acked_ids = []
    while True:
        try:
            request = send_queue.get_nowait()
        except (queue.Empty, asyncio.QueueEmpty):
            return acked_ids
        if request is not None:
            acked_ids.append(request.event_processed.id)


class SubscriptionStaleResponseTests(unittest.TestCase):
    def test_response_for_message_from_replaced_stream_is_dropped(self):
        stub = MagicMock()
        stub.SubscribeTopicEventsAlpha1.side_effect = [
            _FakeTopicStream('111'),
            _FakeTopicStream('222'),
        ]
        subscription = Subscription(stub, 'pubsub', 'topic')
        subscription.start()
        message_stale = subscription.next_message()
        with patch.object(subscription_module.DaprHealth, 'wait_for_sidecar'):
            subscription.reconnect_stream()
        message_current = subscription.next_message()

        with self.assertLogs(subscription_module.logger, level='DEBUG') as logs:
            subscription.respond_success(message_stale)
        subscription.respond_success(message_current)

        self.assertIn('111', logs.output[0])
        self.assertEqual(['222'], _drain_acked_ids(subscription._send_queue))


class SubscriptionAsyncStaleResponseTests(unittest.IsolatedAsyncioTestCase):
    async def test_response_for_message_from_replaced_stream_is_dropped(self):
        stub = MagicMock()
        stub.SubscribeTopicEventsAlpha1.side_effect = [
            _FakeTopicStreamAsync('111'),
            _FakeTopicStreamAsync('222'),
        ]
        subscription = SubscriptionAsync(stub, 'pubsub', 'topic')
        await subscription.start()
        message_stale = await subscription.next_message()
        with patch.object(subscription_async_module.DaprHealth, 'wait_for_sidecar', AsyncMock()):
            await subscription.reconnect_stream()
        message_current = await subscription.next_message()

        with self.assertLogs(subscription_async_module.logger, level='DEBUG') as logs:
            await subscription.respond_success(message_stale)
        await subscription.respond_success(message_current)

        self.assertIn('111', logs.output[0])
        self.assertEqual(['222'], _drain_acked_ids(subscription._send_queue))


class ReconnectBackoffTests(unittest.TestCase):
    def test_backoff_grows_with_jitter_up_to_the_cap(self):
        for module in (subscription_module, subscription_async_module):
            with self.subTest(module=module.__name__):
                initial = module.RECONNECT_BACKOFF_INITIAL_SECONDS
                maximum = module.RECONNECT_BACKOFF_MAX_SECONDS

                backoff_first = module._reconnect_backoff_seconds(1)
                backoff_second = module._reconnect_backoff_seconds(2)
                backoff_late = module._reconnect_backoff_seconds(50)

                self.assertTrue(initial / 2 <= backoff_first <= initial)
                self.assertTrue(initial <= backoff_second <= initial * 2)
                self.assertTrue(maximum / 2 <= backoff_late <= maximum)
