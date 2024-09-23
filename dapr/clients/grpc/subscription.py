import json

from grpc import StreamStreamMultiCallable, RpcError, StatusCode  # type: ignore

from dapr.clients.exceptions import StreamInactiveError
from dapr.clients.grpc._response import TopicEventResponse
from dapr.proto import api_v1, appcallback_v1
import queue
import threading
from typing import Optional


def success():
    return appcallback_v1.TopicEventResponse.SUCCESS


def retry():
    return appcallback_v1.TopicEventResponse.RETRY


def drop():
    return appcallback_v1.TopicEventResponse.DROP


class Subscription:
    def __init__(self, stub, pubsub_name, topic, metadata=None, dead_letter_topic=None):
        self._stub = stub
        self.pubsub_name = pubsub_name
        self.topic = topic
        self.metadata = metadata or {}
        self.dead_letter_topic = dead_letter_topic or ''
        self._stream: Optional[StreamStreamMultiCallable] = None  # Type annotation for gRPC stream
        self._response_thread: Optional[threading.Thread] = None  # Type for thread
        self._send_queue: queue.Queue = queue.Queue()  # Type annotation for send queue
        self._receive_queue: queue.Queue = queue.Queue()  # Type annotation for receive queue
        self._stream_active: bool = False
        self._stream_lock = threading.Lock()  # Protects _stream_active

    def start(self):
        def outgoing_request_iterator():
            """
            Generator function to create the request iterator for the stream
            """
            try:
                # Send InitialRequest needed to establish the stream
                initial_request = api_v1.SubscribeTopicEventsRequestAlpha1(
                    initial_request=api_v1.SubscribeTopicEventsRequestInitialAlpha1(
                        pubsub_name=self.pubsub_name,
                        topic=self.topic,
                        metadata=self.metadata or {},
                        dead_letter_topic=self.dead_letter_topic or '',
                    )
                )
                yield initial_request

                # Start sending back acknowledgement messages from the send queue
                while self._is_stream_active():
                    try:
                        response = self._send_queue.get(timeout=1)
                        # Check again if the stream is still active
                        if not self._is_stream_active():
                            break
                        yield response
                    except queue.Empty:
                        continue
            except Exception as e:
                raise Exception(f'Error in request iterator: {e}')

        # Create the bidirectional stream
        self._stream = self._stub.SubscribeTopicEventsAlpha1(outgoing_request_iterator())
        self._set_stream_active()

        # Start a thread to handle incoming messages
        self._response_thread = threading.Thread(target=self._handle_incoming_messages, daemon=True)
        self._response_thread.start()

    def _handle_incoming_messages(self):
        try:
            # Check if the stream is not None
            if self._stream is not None:
                # The first message dapr sends on the stream is for signalling only, so discard it
                next(self._stream)

                # Read messages from the stream and put them in the receive queue
                for message in self._stream:
                    if self._is_stream_active():
                        self._receive_queue.put(message.event_message)
                    else:
                        break
        except RpcError as e:
            if e.code() != StatusCode.CANCELLED:
                print(f'gRPC error in stream: {e.details()}, Status Code: {e.code()}')
        except Exception as e:
            raise Exception(f'Error while handling responses: {e}')
        finally:
            self._set_stream_inactive()

    def next_message(self, timeout=None):
        msg = self.read_message_from_queue(self._receive_queue, timeout=timeout)

        if msg is None:
            return None

        return SubscriptionMessage(msg)

    def _respond(self, message, status):
        try:
            status = appcallback_v1.TopicEventResponse(status=status.value)
            response = api_v1.SubscribeTopicEventsRequestProcessedAlpha1(
                id=message.id(), status=status
            )
            msg = api_v1.SubscribeTopicEventsRequestAlpha1(event_processed=response)

            self.send_message_to_queue(self._send_queue, msg)
        except Exception as e:
            print(f'Exception in send_message: {e}')

    def respond_success(self, message):
        self._respond(message, TopicEventResponse('success').status)

    def respond_retry(self, message):
        self._respond(message, TopicEventResponse('retry').status)

    def respond_drop(self, message):
        self._respond(message, TopicEventResponse('drop').status)

    def send_message_to_queue(self, q, message):
        if not self._is_stream_active():
            raise StreamInactiveError('Stream is not active')
        q.put(message)

    def read_message_from_queue(self, q, timeout=None):
        if not self._is_stream_active():
            raise StreamInactiveError('Stream is not active')
        try:
            return q.get(timeout=timeout)
        except queue.Empty:
            return None

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
        if not self._is_stream_active():
            return

        self._set_stream_inactive()

        # Cancel the stream
        if self._stream:
            try:
                self._stream.cancel()
            except RpcError as e:
                if e.code() != StatusCode.CANCELLED:
                    raise Exception(f'Error while closing stream: {e}')
            except Exception as e:
                raise Exception(f'Error while closing stream: {e}')

        # Join the response-handling thread to ensure it has finished
        if self._response_thread:
            self._response_thread.join()
            self._response_thread = None


class SubscriptionMessage:
    def __init__(self, msg):
        self._id = msg.id
        self._source = msg.source
        self._type = msg.type
        self._spec_version = msg.spec_version
        self._data_content_type = msg.data_content_type
        self._topic = msg.topic
        self._pubsub_name = msg.pubsub_name
        self._raw_data = msg.data
        self._extensions = msg.extensions
        self._data = None

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
                    pass  # If JSON parsing fails, keep `data` as None
            elif self._data_content_type == 'text/plain':
                # Assume UTF-8 encoding
                try:
                    self._data = self._raw_data.decode('utf-8')
                except UnicodeDecodeError:
                    pass
            elif self._data_content_type.startswith(
                'application/'
            ) and self._data_content_type.endswith('+json'):
                # Handle custom JSON-based media types (e.g., application/vnd.api+json)
                try:
                    self._data = json.loads(self._raw_data)
                except json.JSONDecodeError:
                    pass  # If JSON parsing fails, keep `data` as None
        except Exception as e:
            # Log or handle any unexpected exceptions
            print(f'Error parsing media type: {e}')
