import json

from google.protobuf.json_format import MessageToDict
from grpc import RpcError, StatusCode, Call  # type: ignore

from dapr.clients.grpc._response import TopicEventResponse
from dapr.clients.health import DaprHealth
from dapr.proto import api_v1, appcallback_v1
import queue
import threading
from typing import Optional, Union

from dapr.proto.runtime.v1.appcallback_pb2 import TopicEventRequest


class Subscription:
    SUCCESS = TopicEventResponse('success').status
    RETRY = TopicEventResponse('retry').status
    DROP = TopicEventResponse('drop').status

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
        next(self._stream)  # discard the initial message

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
        if not self._is_stream_active():
            raise StreamInactiveError('Stream is not active')

        try:
            # Read the next message from the stream directly
            if self._stream is not None:
                message = next(self._stream, None)
                if message is None:
                    return None
                return SubscriptionMessage(message.event_message)
        except RpcError as e:
            if e.code() == StatusCode.UNAVAILABLE:
                print(
                    f'gRPC error while reading from stream: {e.details()}, Status Code: {e.code()}'
                )
                self.reconnect_stream()
            elif e.code() != StatusCode.CANCELLED:
                raise Exception(
                    f'gRPC error while reading from subscription stream: {e.details()} '
                    f'Status Code: {e.code()}'
                )
        except Exception as e:
            raise Exception(f'Error while fetching message: {e}')

        return None

    def _respond(self, message, status):
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
        self._respond(message, self.SUCCESS)

    def respond_retry(self, message):
        self._respond(message, self.RETRY)

    def respond_drop(self, message):
        self._respond(message, self.DROP)

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


class SubscriptionMessage:
    def __init__(self, msg: TopicEventRequest):
        self._id: str = msg.id
        self._source: str = msg.source
        self._type: str = msg.type
        self._spec_version: str = msg.spec_version
        self._data_content_type: str = msg.data_content_type
        self._topic: str = msg.topic
        self._pubsub_name: str = msg.pubsub_name
        self._raw_data: bytes = msg.data
        self._data: Optional[Union[dict, str]] = None

        try:
            self._extensions = MessageToDict(msg.extensions)
        except Exception as e:
            self._extensions = {}
            print(f'Error parsing extensions: {e}')

        # Parse the content based on its media type
        if self._raw_data and len(self._raw_data) > 0:
            self._parse_data_content()

    def id(self):
        return self._id

    def source(self):
        return self._source

    def type(self):
        return self._type

    def spec_version(self):
        return self._spec_version

    def data_content_type(self):
        return self._data_content_type

    def topic(self):
        return self._topic

    def pubsub_name(self):
        return self._pubsub_name

    def raw_data(self):
        return self._raw_data

    def extensions(self):
        return self._extensions

    def data(self):
        return self._data

    def _parse_data_content(self):
        try:
            if self._data_content_type == 'application/json':
                try:
                    self._data = json.loads(self._raw_data)
                except json.JSONDecodeError:
                    print(f'Error parsing json message data from topic {self._topic}')
                    pass  # If JSON parsing fails, keep `data` as None
            elif self._data_content_type == 'text/plain':
                # Assume UTF-8 encoding
                try:
                    self._data = self._raw_data.decode('utf-8')
                except UnicodeDecodeError:
                    print(f'Error decoding message data from topic {self._topic} as UTF-8')
            elif self._data_content_type.startswith(
                'application/'
            ) and self._data_content_type.endswith('+json'):
                # Handle custom JSON-based media types (e.g., application/vnd.api+json)
                try:
                    self._data = json.loads(self._raw_data)
                except json.JSONDecodeError:
                    print(f'Error parsing json message data from topic {self._topic}')
                    pass  # If JSON parsing fails, keep `data` as None
        except Exception as e:
            # Log or handle any unexpected exceptions
            print(f'Error parsing media type: {e}')


class StreamInactiveError(Exception):
    pass
