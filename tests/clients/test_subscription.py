import asyncio
import queue
import sys
import threading
import unittest
from collections.abc import Iterator
from unittest.mock import AsyncMock, MagicMock, patch

from google.protobuf.struct_pb2 import Struct
from grpc import RpcError, StatusCode
from grpc.aio import AioRpcError

from dapr.aio.clients.grpc import subscription as subscription_async_module
from dapr.aio.clients.grpc.subscription import Subscription as SubscriptionAsync
from dapr.clients.grpc import subscription as subscription_module
from dapr.clients.grpc.subscription import StreamInactiveError, Subscription, SubscriptionMessage
from dapr.common.pubsub.subscription import StreamReconnectError
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


class _UnavailableRpcError(RpcError):
    def code(self) -> StatusCode:
        return StatusCode.UNAVAILABLE

    def details(self) -> str:
        return 'sidecar unavailable'


class _FailingInitialReadCall:
    """Fake bidi call whose initial read fails with UNAVAILABLE."""

    def __init__(self) -> None:
        self.cancelled = False

    def __next__(self) -> api_v1.SubscribeTopicEventsResponseAlpha1:
        raise _UnavailableRpcError()

    def cancel(self) -> bool:
        self.cancelled = True
        return True


class _FailingAfterInitialReadCall(_EagerStreamCall):
    """Fake bidi call that sends the initial response, then fails with UNAVAILABLE."""

    def __next__(self) -> api_v1.SubscribeTopicEventsResponseAlpha1:
        try:
            return super().__next__()
        except StopIteration:
            raise _UnavailableRpcError() from None


class _ConsumingStub(_EagerStub):
    """Eager stub that hands back a call built by ``call_factory``."""

    def __init__(self, call_factory) -> None:
        super().__init__()
        self._call_factory = call_factory

    def SubscribeTopicEventsAlpha1(self, request_iterator: Iterator):
        super().SubscribeTopicEventsAlpha1(request_iterator)
        return self._call_factory()


class SubscriptionStartFailureTests(unittest.TestCase):
    def test_request_iterator_exits_when_initial_read_fails(self):
        stub = _ConsumingStub(_FailingInitialReadCall)
        subscription = Subscription(stub, 'pubsub', 'topic')

        with self.assertRaisesRegex(Exception, 'Error while initializing stream'):
            subscription.start()

        self.assertTrue(stub.iterator_exhausted.wait(timeout=_TEST_TIMEOUT_SECONDS))

    def test_close_while_opening_stream_cancels_the_new_stream(self):
        stream = _EagerStreamCall()
        stub = MagicMock()
        subscription = Subscription(stub, 'pubsub', 'topic')

        def open_stream_while_closing(request_iterator: Iterator) -> _EagerStreamCall:
            subscription.close()
            return stream

        stub.SubscribeTopicEventsAlpha1.side_effect = open_stream_while_closing

        with self.assertRaises(StreamInactiveError):
            subscription.start()
        self.assertTrue(stream.cancelled)

    def test_failed_reconnect_counts_as_an_attempt(self):
        calls = iter([_FailingAfterInitialReadCall()])
        stub = MagicMock()
        stub.SubscribeTopicEventsAlpha1.side_effect = lambda _: next(
            calls, _FailingInitialReadCall()
        )
        subscription = Subscription(stub, 'pubsub', 'topic')
        subscription.start()

        with (
            patch.object(subscription_module.DaprHealth, 'wait_for_sidecar'),
            patch.object(
                subscription_module, '_reconnect_backoff_seconds', return_value=0
            ) as backoff,
        ):
            with self.assertRaisesRegex(StreamReconnectError, 'sidecar unavailable'):
                subscription.next_message()

        max_attempts = subscription_module.MAX_RECONNECT_ATTEMPTS
        backoff_attempts = [call.args[0] for call in backoff.call_args_list]
        self.assertEqual(1 + max_attempts, stub.SubscribeTopicEventsAlpha1.call_count)
        self.assertEqual(list(range(1, max_attempts)), backoff_attempts)


class _FailingInitialReadAsync:
    def __init__(self, error: BaseException) -> None:
        self._error = error

    async def read(self):
        raise self._error

    def cancel(self) -> bool:
        return True


class _InitialReadThenUnavailableAsync:
    def __init__(self) -> None:
        self._initial_read_done = False

    async def read(self):
        if self._initial_read_done:
            raise AioRpcError(StatusCode.UNAVAILABLE, None, None, 'sidecar unavailable')
        self._initial_read_done = True
        return api_v1.SubscribeTopicEventsResponseAlpha1()

    def cancel(self) -> bool:
        return True


class _TaskCancelledWhileClosingAsync:
    def __init__(self, subscription: SubscriptionAsync) -> None:
        self._subscription = subscription

    async def read(self):
        await self._subscription.close()
        current_task = asyncio.current_task()
        assert current_task is not None
        current_task.cancel()
        await asyncio.sleep(0)

    def cancel(self) -> bool:
        return True


class SubscriptionAsyncStartFailureTests(unittest.IsolatedAsyncioTestCase):
    async def test_failed_start_marks_stream_inactive_and_releases_iterator(self):
        stub = MagicMock()
        error = AioRpcError(StatusCode.UNAVAILABLE, None, None, 'sidecar unavailable')
        stub.SubscribeTopicEventsAlpha1.return_value = _FailingInitialReadAsync(error)
        subscription = SubscriptionAsync(stub, 'pubsub', 'topic')

        with self.assertRaises(AioRpcError):
            await subscription.start()

        self.assertFalse(subscription._stream_active.is_set())
        self.assertIsNone(subscription._send_queue.get_nowait())

    @unittest.skipIf(sys.version_info < (3, 11), 'Task.cancelling() needs Python 3.11+')
    async def test_task_cancellation_propagates_when_close_races_it(self):
        stub = MagicMock()
        subscription = SubscriptionAsync(stub, 'pubsub', 'topic')
        stream = _TaskCancelledWhileClosingAsync(subscription)
        stub.SubscribeTopicEventsAlpha1.return_value = stream

        start_task = asyncio.create_task(subscription.start())

        with self.assertRaises(asyncio.CancelledError):
            await start_task

    async def test_failed_reconnect_counts_as_an_attempt(self):
        error = AioRpcError(StatusCode.UNAVAILABLE, None, None, 'sidecar unavailable')
        calls = iter([_InitialReadThenUnavailableAsync()])
        stub = MagicMock()
        stub.SubscribeTopicEventsAlpha1.side_effect = lambda _: next(
            calls, _FailingInitialReadAsync(error)
        )
        subscription = SubscriptionAsync(stub, 'pubsub', 'topic')
        await subscription.start()

        with (
            patch.object(subscription_async_module.DaprHealth, 'wait_for_sidecar', AsyncMock()),
            patch.object(
                subscription_async_module, '_reconnect_backoff_seconds', return_value=0
            ) as backoff,
        ):
            with self.assertRaisesRegex(StreamReconnectError, 'sidecar unavailable'):
                await subscription.next_message()

        max_attempts = subscription_async_module.MAX_RECONNECT_ATTEMPTS
        backoff_attempts = [call.args[0] for call in backoff.call_args_list]
        self.assertEqual(1 + max_attempts, stub.SubscribeTopicEventsAlpha1.call_count)
        self.assertEqual(list(range(1, max_attempts)), backoff_attempts)
