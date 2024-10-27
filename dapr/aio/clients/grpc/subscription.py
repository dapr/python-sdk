import asyncio
from grpc import StatusCode
from grpc.aio import AioRpcError

from dapr.clients.grpc._response import TopicEventResponse
from dapr.clients.health import DaprHealth
from dapr.common.pubsub.subscription import (
    StreamInactiveError,
    SubscriptionMessage,
    StreamCancelledError,
)
from dapr.proto import api_v1, appcallback_v1


class Subscription:
    def __init__(self, stub, pubsub_name, topic, metadata=None, dead_letter_topic=None):
        self._stub = stub
        self._pubsub_name = pubsub_name
        self._topic = topic
        self._metadata = metadata or {}
        self._dead_letter_topic = dead_letter_topic or ''
        self._stream = None
        self._send_queue = asyncio.Queue()
        self._stream_active = asyncio.Event()

    async def start(self):
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
                        response = await asyncio.wait_for(self._send_queue.get(), timeout=1.0)
                        yield response
                    except asyncio.TimeoutError:
                        continue
            except Exception as e:
                raise Exception(f'Error while writing to stream: {e}')

        self._stream = self._stub.SubscribeTopicEventsAlpha1(outgoing_request_iterator())
        self._stream_active.set()
        await self._stream.read()  # discard the initial message

    async def reconnect_stream(self):
        await self.close()
        DaprHealth.wait_until_ready()
        print('Attempting to reconnect...')
        await self.start()

    async def next_message(self):
        if not self._stream_active.is_set():
            raise StreamInactiveError('Stream is not active')

        try:
            if self._stream is not None:
                message = await self._stream.read()
                if message is None:
                    return None
                return SubscriptionMessage(message.event_message)
        except AioRpcError as e:
            if e.code() == StatusCode.UNAVAILABLE:
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

        return None

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
        if self._stream:
            try:
                self._stream.cancel()
                self._stream_active.clear()
            except AioRpcError as e:
                if e.code() != StatusCode.CANCELLED:
                    raise Exception(f'Error while closing stream: {e}')
            except Exception as e:
                raise Exception(f'Error while closing stream: {e}')
