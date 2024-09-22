import grpc

from dapr.clients.exceptions import StreamInactiveError
from dapr.clients.grpc._response import TopicEventResponse
from dapr.proto import api_v1, appcallback_v1
import queue
import threading


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
        self._stream = None
        self._response_thread = None
        self._send_queue = queue.Queue()
        self._receive_queue = queue.Queue()
        self._stream_active = False
        self._stream_lock = threading.Lock()  # Protects _stream_active

    def start(self):
        def request_iterator():
            try:
                # Send InitialRequest needed to establish the stream
                initial_request = api_v1.SubscribeTopicEventsRequestAlpha1(
                    initial_request=api_v1.SubscribeTopicEventsRequestInitialAlpha1(
                        pubsub_name=self.pubsub_name, topic=self.topic, metadata=self.metadata or {},
                        dead_letter_topic=self.dead_letter_topic or ''))
                yield initial_request

                while self._is_stream_active():
                    try:
                        yield self._send_queue.get()  # TODO Should I add a timeout?
                    except queue.Empty:
                        continue
            except Exception as e:
                raise Exception(f"Error in request iterator: {e}")

        # Create the bidirectional stream
        self._stream = self._stub.SubscribeTopicEventsAlpha1(request_iterator())
        self._set_stream_active()

        # Start a thread to handle incoming messages
        self._response_thread = threading.Thread(target=self._handle_responses, daemon=True)
        self._response_thread.start()

    def _handle_responses(self):
        try:
            # The first message dapr sends on the stream is for signalling only, so discard it
            next(self._stream)

            # Read messages from the stream and put them in the receive queue
            for message in self._stream:
                if self._is_stream_active():
                    self._receive_queue.put(message.event_message)
                else:
                    break
        except grpc.RpcError as e:
            if e.code() != grpc.StatusCode.CANCELLED:
                print(f"gRPC error in stream: {e.details()}, Status Code: {e.code()}")
        except Exception as e:
            raise Exception(f"Error while handling responses: {e}")
        finally:
            self._set_stream_inactive()

    def next_message(self, timeout=1):
        """
        Gets the next message from the receive queue
        @param timeout: Timeout in seconds
        @return: The next message
        """
        return self.read_message_from_queue(self._receive_queue, timeout=timeout)

    def _respond(self, message, status):
        try:
            status = appcallback_v1.TopicEventResponse(status=status.value)
            response = api_v1.SubscribeTopicEventsRequestProcessedAlpha1(id=message.id,
                                                                         status=status)
            msg = api_v1.SubscribeTopicEventsRequestAlpha1(event_processed=response)

            self.send_message_to_queue(self._send_queue, msg)
        except Exception as e:
            print(f"Exception in send_message: {e}")

    def respond_success(self, message):
        self._respond(message, TopicEventResponse('success').status)

    def respond_retry(self, message):
        self._respond(message, TopicEventResponse('retry').status)

    def respond_drop(self, message):
        self._respond(message, TopicEventResponse('drop').status)

    def send_message_to_queue(self, q, message):
        if not self._is_stream_active():
            raise StreamInactiveError("Stream is not active")
        q.put(message)

    def read_message_from_queue(self, q, timeout):
        if not self._is_stream_active():
            raise StreamInactiveError("Stream is not active")
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
            except grpc.RpcError as e:
                if e.code() != grpc.StatusCode.CANCELLED:
                    raise Exception(f"Error while closing stream: {e}")
            except Exception as e:
                raise Exception(f"Error while closing stream: {e}")

        # Join the response-handling thread to ensure it has finished
        if self._response_thread:
            self._response_thread.join()
            self._response_thread = None

