import asyncio
from typing import Optional

from grpc import StatusCode  # type: ignore[attr-defined]
from grpc.aio import AioRpcError

from dapr.aio.clients.health import DaprHealth
from dapr.clients.grpc._response import TopicEventResponse
from dapr.common.pubsub.subscription import (
    StreamCancelledError,
    StreamInactiveError,
    SubscriptionMessage,
)
from dapr.proto import api_v1, appcallback_v1

MAX_RECONNECT_ATTEMPTS = 5


class Subscription:
    def __init__(self, stub, pubsub_name, topic, metadata=None, dead_letter_topic=None):
        self._stub = stub
        self._pubsub_name = pubsub_name
        self._topic = topic
        self._metadata = metadata or {}
        self._dead_letter_topic = dead_letter_topic or ''
        self._stream = None
        self._send_queue: asyncio.Queue[Optional[api_v1.SubscribeTopicEventsRequestAlpha1]] = (
            asyncio.Queue()
        )
        self._stream_active = asyncio.Event()
        self._closed = False

    async def start(self):
        if self._closed:
            raise StreamInactiveError('Stream is not active')
        send_queue: asyncio.Queue[Optional[api_v1.SubscribeTopicEventsRequestAlpha1]] = (
            asyncio.Queue()
        )

        async def outgoing_request_iterator():
            try:
                initial_request = api_v1.SubscribeTopicEventsRequestAlpha1(
                    initial_request=api_v1.SubscribeTopicEventsRequestInitialAlpha1(
                        pubsub_name=self._pubsub_name,
                        topic=self._topic,
                        metadata=self._metadata,
                        dead_letter_topic=self._dead_letter_topic,
                    )
                )
                yield initial_request

                while self._stream_active.is_set():
                    try:
                        response = await asyncio.wait_for(send_queue.get(), timeout=1.0)
                        if response is None:
                            return
                        yield response
                    except asyncio.TimeoutError:
                        continue
            except Exception as e:
                raise Exception(f'Error while writing to stream: {e}')

        # The stream gets its own send queue, so the request iterator of a stream that already
        # failed can't take its acks.
        self._send_queue = send_queue
        self._stream = self._stub.SubscribeTopicEventsAlpha1(outgoing_request_iterator())
        self._stream_active.set()
        await self._stream.read()  # discard the initial message

    async def reconnect_stream(self):
        await self._close_stream()
        await DaprHealth.wait_for_sidecar()
        print('Attempting to reconnect...')
        await self.start()

    async def next_message(self):
        """Get the next message from the stream.

        On a transient stream error the stream is reconnected and read again, up to
        MAX_RECONNECT_ATTEMPTS times per call.

        Returns:
            Optional[SubscriptionMessage]: The next message, or None if the stream ended.

        Raises:
            StreamInactiveError: If the subscription is closed.
            StreamCancelledError: If the stream was cancelled.
            Exception: On any other error, or if the stream still fails after the reconnects.
        """
        reconnect_attempts = 0
        while True:
            if not self._stream_active.is_set() or self._stream is None:
                raise StreamInactiveError('Stream is not active')

            try:
                message = await self._stream.read()
                if message is None:
                    return None
                return SubscriptionMessage(message.event_message)
            except AioRpcError as e:
                if e.code() in (StatusCode.UNAVAILABLE, StatusCode.UNKNOWN, StatusCode.INTERNAL):
                    if reconnect_attempts >= MAX_RECONNECT_ATTEMPTS:
                        raise Exception(
                            f'Subscription stream still failing after {reconnect_attempts} '
                            f'reconnect attempts: {e.details()} Status Code: {e.code()}'
                        )
                    reconnect_attempts += 1
                    print(
                        f'gRPC error while reading from stream: {e.details()}, '
                        f'Status Code: {e.code()}. '
                        f'Attempting to reconnect...'
                    )
                    await self.reconnect_stream()
                elif e.code() == StatusCode.CANCELLED:
                    raise StreamCancelledError('Stream has been cancelled')
                else:
                    raise Exception(f'gRPC error while reading from subscription stream: {e} ')
            except Exception as e:
                raise Exception(f'Error while fetching message: {e}')

    async def respond(self, message, status):
        try:
            status = appcallback_v1.TopicEventResponse(status=status.value)
            response = api_v1.SubscribeTopicEventsRequestProcessedAlpha1(
                id=message.id(), status=status
            )
            msg = api_v1.SubscribeTopicEventsRequestAlpha1(event_processed=response)
            if not self._stream_active.is_set():
                raise StreamInactiveError('Stream is not active')
            await self._send_queue.put(msg)
        except Exception as e:
            print(f"Can't send message: {e}")

    async def respond_success(self, message):
        await self.respond(message, TopicEventResponse('success').status)

    async def respond_retry(self, message):
        await self.respond(message, TopicEventResponse('retry').status)

    async def respond_drop(self, message):
        await self.respond(message, TopicEventResponse('drop').status)

    async def close(self):
        self._closed = True
        await self._close_stream()

    async def _close_stream(self):
        self._send_queue.put_nowait(None)
        if self._stream:
            try:
                self._stream.cancel()
                self._stream_active.clear()
            except AioRpcError as e:
                if e.code() != StatusCode.CANCELLED:
                    raise Exception(f'Error while closing stream: {e}')
            except Exception as e:
                raise Exception(f'Error while closing stream: {e}')

    def __aiter__(self):
        """Make the subscription async iterable."""
        return self

    async def __anext__(self):
        return await self.next_message()
