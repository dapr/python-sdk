import grpc
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
        self._send_queue = queue.Queue()
        self._receive_queue = queue.Queue()
        self._stream_active = False

    def start(self):
        def request_iterator():
            try:
                # Send InitialRequest needed to establish the stream
                initial_request = api_v1.SubscribeTopicEventsRequestAlpha1(
                    initial_request=api_v1.SubscribeTopicEventsRequestInitialAlpha1(
                        pubsub_name=self.pubsub_name, topic=self.topic, metadata=self.metadata or {},
                        dead_letter_topic=self.dead_letter_topic or ''))
                yield initial_request

                while self._stream_active:
                    try:
                        request = self._send_queue.get()
                        if request is None:
                            break

                        yield request
                    except queue.Empty:
                        continue
            except Exception as e:
                print(f"Exception in request_iterator: {e}")
                raise e

        # Create the bidirectional stream
        self._stream = self._stub.SubscribeTopicEventsAlpha1(request_iterator())
        self._stream_active = True

        # Start a thread to handle incoming messages
        threading.Thread(target=self._handle_responses, daemon=True).start()

    def _handle_responses(self):
        try:
            # The first message dapr sends on the stream is for signalling only, so discard it
            next(self._stream)

            for msg in self._stream:
                print(f"Received message from dapr on stream: {msg.event_message.id}") # SubscribeTopicEventsResponseAlpha1
                self._receive_queue.put(msg.event_message)
        except grpc.RpcError as e:
            print(f"gRPC error in stream: {e}")
        except Exception as e:
            print(f"Unexpected error in stream: {e}")
        finally:
            self._stream_active = False

    def next_message(self, timeout=None):
        print("in next_message")
        try:
            return self._receive_queue.get(timeout=timeout)
        except queue.Empty as e :
            print("queue empty", e)
            return None
        except Exception as e:
            print(f"Exception in next_message: {e}")
            return None

    def respond(self, message, status):
        try:
            status = appcallback_v1.TopicEventResponse(status=status.value)
            response = api_v1.SubscribeTopicEventsRequestProcessedAlpha1(id=message.id,
                                                                         status=status)
            msg = api_v1.SubscribeTopicEventsRequestAlpha1(event_processed=response)

            self._send_queue.put(msg)
        except Exception as e:
            print(f"Exception in send_message: {e}")

    def close(self):
        self._stream_active = False
        self._send_queue.put(None)
        if self._stream:
            self._stream.cancel()