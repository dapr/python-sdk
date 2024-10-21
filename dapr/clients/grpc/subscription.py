from grpc import RpcError, StatusCode, Call  # type: ignore

from dapr.clients.grpc._response import TopicEventResponse
from dapr.clients.health import DaprHealth
from dapr.common.pubsub.subscription import (
    StreamInactiveError,
    SubscriptionMessage,
    StreamCancelledError,
)
from dapr.proto import api_v1, appcallback_v1
import queue
import threading
from typing import Optional


class Subscription:
    def __init__(self, stub, pubsub_name, topic, metadata=None, dead_letter_topic=None):
        self._stub = stub
        self._pubsub_name = pubsub_name
        self._topic = topic
        self._metadata = metadata or {}
        self._dead_letter_topic = dead_letter_topic or ''
        self._stream: Optional[Call] = None
        self._response_thread: Optional[threading.Thread] = None
        self._send_queue: queue.Queue = queue.Queue()
        self._stream_active: bool = False
        self._stream_lock = threading.Lock()  # Protects _stream_active

    def start(self):
        def outgoing_request_iterator():
            """
            Generator function to create the request iterator for the stream.
            This sends the initial request to establish the stream.
            """
            try:
                # Send InitialRequest needed to establish the stream
                initial_request = api_v1.SubscribeTopicEventsRequestAlpha1(
                    initial_request=api_v1.SubscribeTopicEventsRequestInitialAlpha1(
                        pubsub_name=self._pubsub_name,
                        topic=self._topic,
                        metadata=self._metadata or {},
                        dead_letter_topic=self._dead_letter_topic or '',
                    )
                )
                yield initial_request

                # Start sending back acknowledgement messages from the send queue
                while self._is_stream_active():
                    try:
                        # Wait for responses/acknowledgements to send from the send queue.
                        response = self._send_queue.get()
                        yield response
                    except queue.Empty:
                        continue
            except Exception as e:
                raise Exception(f'Error while writing to stream: {e}')

        # Create the bidirectional stream
        self._stream = self._stub.SubscribeTopicEventsAlpha1(outgoing_request_iterator())
        self._set_stream_active()
        try:
            next(self._stream)  # discard the initial message
        except Exception as e:
            raise Exception(f'Error while initializing stream: {e}')

    def reconnect_stream(self):
        self.close()
        DaprHealth.wait_until_ready()
        print('Attempting to reconnect...')
        self.start()

    def next_message(self):
        """
        Get the next message from the receive queue.
        @return: The next message from the queue,
                 or None if no message is received within the timeout.
        """
        if not self._is_stream_active() or self._stream is None:
            raise StreamInactiveError('Stream is not active')

        try:
            # Read the next message from the stream directly
            message = next(self._stream)
            return SubscriptionMessage(message.event_message)
        except RpcError as e:
            # If Dapr can't be reached, wait until it's ready and reconnect the stream
            if e.code() == StatusCode.UNAVAILABLE:
                print(
                    f'gRPC error while reading from stream: {e.details()}, Status Code: {e.code()}'
                )
                self.reconnect_stream()
            elif e.code() == StatusCode.CANCELLED:
                raise StreamCancelledError('Stream has been cancelled')
            else:
                raise Exception(
                    f'gRPC error while reading from subscription stream: {e.details()} '
                    f'Status Code: {e.code()}'
                )
        except Exception as e:
            raise Exception(f'Error while fetching message: {e}')

    def respond(self, message, status):
        try:
            status = appcallback_v1.TopicEventResponse(status=status.value)
            response = api_v1.SubscribeTopicEventsRequestProcessedAlpha1(
                id=message.id(), status=status
            )
            msg = api_v1.SubscribeTopicEventsRequestAlpha1(event_processed=response)
            if not self._is_stream_active():
                raise StreamInactiveError('Stream is not active')
            self._send_queue.put(msg)
        except Exception as e:
            print(f"Can't send message on inactive stream: {e}")

    def respond_success(self, message):
        self.respond(message, TopicEventResponse('success').status)

    def respond_retry(self, message):
        self.respond(message, TopicEventResponse('retry').status)

    def respond_drop(self, message):
        self.respond(message, TopicEventResponse('drop').status)

    def _set_stream_active(self):
        with self._stream_lock:
            self._stream_active = True

    def _set_stream_inactive(self):
        with self._stream_lock:
            self._stream_active = False

    def _is_stream_active(self):
        with self._stream_lock:
            return self._stream_active

    def close(self):
        if self._stream:
            try:
                self._stream.cancel()
                self._set_stream_inactive()
            except RpcError as e:
                if e.code() != StatusCode.CANCELLED:
                    raise Exception(f'Error while closing stream: {e}')
            except Exception as e:
                raise Exception(f'Error while closing stream: {e}')
