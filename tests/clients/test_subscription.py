import queue
import threading
import unittest
from collections.abc import Iterator

from google.protobuf.struct_pb2 import Struct

from dapr.clients.grpc.subscription import Subscription, SubscriptionMessage
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


class _EagerStreamCall:
    """Fake bidi call that yields the initial response and records cancellation."""

    def __init__(self) -> None:
        self.cancelled = False
        self._responses = iter([api_v1.SubscribeTopicEventsResponseAlpha1()])

    def __iter__(self) -> '_EagerStreamCall':
        return self

    def __next__(self) -> api_v1.SubscribeTopicEventsResponseAlpha1:
        return next(self._responses)

    def cancel(self) -> bool:
        self.cancelled = True
        return True


class _EagerStub:
    """Fake stub that drains the request iterator on a background thread before returning.

    This mimics gRPC's request-consumer thread pulling from the iterator before
    ``SubscribeTopicEventsAlpha1`` hands the call back to the caller.
    """

    def __init__(self) -> None:
        self.requests: queue.Queue = queue.Queue()
        self.iterator_exhausted = threading.Event()

    def SubscribeTopicEventsAlpha1(self, request_iterator: Iterator) -> _EagerStreamCall:
        first_request_pulled = threading.Event()

        def consume() -> None:
            for request in request_iterator:
                self.requests.put(request)
                first_request_pulled.set()
            self.iterator_exhausted.set()

        threading.Thread(target=consume, daemon=True).start()
        first_request_pulled.wait(timeout=_TEST_TIMEOUT_SECONDS)
        # Give the consumer a chance to re-check the stream state before we return.
        self.iterator_exhausted.wait(timeout=0.2)
        return _EagerStreamCall()


_TEST_TIMEOUT_SECONDS = 5


class SubscriptionStreamTests(unittest.TestCase):
    def test_request_stream_stays_open_when_consumer_runs_before_start_returns(self):
        stub = _EagerStub()
        subscription = Subscription(stub, 'pubsub', 'topic')
        subscription.start()
        try:
            self.assertFalse(
                stub.iterator_exhausted.is_set(),
                'request iterator ended right after the initial request, half-closing the stream',
            )

            initial_request = stub.requests.get(timeout=_TEST_TIMEOUT_SECONDS)
            self.assertTrue(initial_request.HasField('initial_request'))

            event_message = SubscriptionMessage(TopicEventRequest(id='msg-1'))
            subscription.respond_success(event_message)

            ack_request = stub.requests.get(timeout=_TEST_TIMEOUT_SECONDS)
            self.assertEqual('msg-1', ack_request.event_processed.id)
        finally:
            subscription.close()

    def test_request_iterator_exits_after_close(self):
        stub = _EagerStub()
        subscription = Subscription(stub, 'pubsub', 'topic')
        subscription.start()
        subscription.close()

        self.assertTrue(stub.iterator_exhausted.wait(timeout=_TEST_TIMEOUT_SECONDS))
