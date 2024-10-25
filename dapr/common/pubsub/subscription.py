import json
from google.protobuf.json_format import MessageToDict
from dapr.proto.runtime.v1.appcallback_pb2 import TopicEventRequest
from typing import Optional, Union


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


class StreamCancelledError(Exception):
    pass
