"""
@generated by mypy-protobuf.  Do not edit manually!
isort:skip_file

Copyright 2021 The Dapr Authors
Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at
http://www.apache.org/licenses/LICENSE-2.0
Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
"""
import builtins
import collections.abc
import dapr.proto.common.v1.common_pb2
import google.protobuf.descriptor
import google.protobuf.internal.containers
import google.protobuf.internal.enum_type_wrapper
import google.protobuf.message
import google.protobuf.struct_pb2
import sys
import typing

if sys.version_info >= (3, 10):
    import typing as typing_extensions
else:
    import typing_extensions

DESCRIPTOR: google.protobuf.descriptor.FileDescriptor

class TopicEventRequest(google.protobuf.message.Message):
    """TopicEventRequest message is compatible with CloudEvent spec v1.0
    https://github.com/cloudevents/spec/blob/v1.0/spec.md
    """

    DESCRIPTOR: google.protobuf.descriptor.Descriptor

    ID_FIELD_NUMBER: builtins.int
    SOURCE_FIELD_NUMBER: builtins.int
    TYPE_FIELD_NUMBER: builtins.int
    SPEC_VERSION_FIELD_NUMBER: builtins.int
    DATA_CONTENT_TYPE_FIELD_NUMBER: builtins.int
    DATA_FIELD_NUMBER: builtins.int
    TOPIC_FIELD_NUMBER: builtins.int
    PUBSUB_NAME_FIELD_NUMBER: builtins.int
    PATH_FIELD_NUMBER: builtins.int
    EXTENSIONS_FIELD_NUMBER: builtins.int
    id: builtins.str
    """id identifies the event. Producers MUST ensure that source + id 
    is unique for each distinct event. If a duplicate event is re-sent
    (e.g. due to a network error) it MAY have the same id.
    """
    source: builtins.str
    """source identifies the context in which an event happened.
    Often this will include information such as the type of the
    event source, the organization publishing the event or the process
    that produced the event. The exact syntax and semantics behind
    the data encoded in the URI is defined by the event producer.
    """
    type: builtins.str
    """The type of event related to the originating occurrence."""
    spec_version: builtins.str
    """The version of the CloudEvents specification."""
    data_content_type: builtins.str
    """The content type of data value."""
    data: builtins.bytes
    """The content of the event."""
    topic: builtins.str
    """The pubsub topic which publisher sent to."""
    pubsub_name: builtins.str
    """The name of the pubsub the publisher sent to."""
    path: builtins.str
    """The matching path from TopicSubscription/routes (if specified) for this event.
    This value is used by OnTopicEvent to "switch" inside the handler.
    """
    @property
    def extensions(self) -> google.protobuf.struct_pb2.Struct:
        """The map of additional custom properties to be sent to the app. These are considered to be cloud event extensions."""
    def __init__(
        self,
        *,
        id: builtins.str = ...,
        source: builtins.str = ...,
        type: builtins.str = ...,
        spec_version: builtins.str = ...,
        data_content_type: builtins.str = ...,
        data: builtins.bytes = ...,
        topic: builtins.str = ...,
        pubsub_name: builtins.str = ...,
        path: builtins.str = ...,
        extensions: google.protobuf.struct_pb2.Struct | None = ...,
    ) -> None: ...
    def HasField(self, field_name: typing_extensions.Literal["extensions", b"extensions"]) -> builtins.bool: ...
    def ClearField(self, field_name: typing_extensions.Literal["data", b"data", "data_content_type", b"data_content_type", "extensions", b"extensions", "id", b"id", "path", b"path", "pubsub_name", b"pubsub_name", "source", b"source", "spec_version", b"spec_version", "topic", b"topic", "type", b"type"]) -> None: ...

global___TopicEventRequest = TopicEventRequest

class TopicEventResponse(google.protobuf.message.Message):
    """TopicEventResponse is response from app on published message"""

    DESCRIPTOR: google.protobuf.descriptor.Descriptor

    class _TopicEventResponseStatus:
        ValueType = typing.NewType("ValueType", builtins.int)
        V: typing_extensions.TypeAlias = ValueType

    class _TopicEventResponseStatusEnumTypeWrapper(google.protobuf.internal.enum_type_wrapper._EnumTypeWrapper[TopicEventResponse._TopicEventResponseStatus.ValueType], builtins.type):  # noqa: F821
        DESCRIPTOR: google.protobuf.descriptor.EnumDescriptor
        SUCCESS: TopicEventResponse._TopicEventResponseStatus.ValueType  # 0
        """SUCCESS is the default behavior: message is acknowledged and not retried or logged."""
        RETRY: TopicEventResponse._TopicEventResponseStatus.ValueType  # 1
        """RETRY status signals Dapr to retry the message as part of an expected scenario (no warning is logged)."""
        DROP: TopicEventResponse._TopicEventResponseStatus.ValueType  # 2
        """DROP status signals Dapr to drop the message as part of an unexpected scenario (warning is logged)."""

    class TopicEventResponseStatus(_TopicEventResponseStatus, metaclass=_TopicEventResponseStatusEnumTypeWrapper):
        """TopicEventResponseStatus allows apps to have finer control over handling of the message."""

    SUCCESS: TopicEventResponse.TopicEventResponseStatus.ValueType  # 0
    """SUCCESS is the default behavior: message is acknowledged and not retried or logged."""
    RETRY: TopicEventResponse.TopicEventResponseStatus.ValueType  # 1
    """RETRY status signals Dapr to retry the message as part of an expected scenario (no warning is logged)."""
    DROP: TopicEventResponse.TopicEventResponseStatus.ValueType  # 2
    """DROP status signals Dapr to drop the message as part of an unexpected scenario (warning is logged)."""

    STATUS_FIELD_NUMBER: builtins.int
    status: global___TopicEventResponse.TopicEventResponseStatus.ValueType
    """The list of output bindings."""
    def __init__(
        self,
        *,
        status: global___TopicEventResponse.TopicEventResponseStatus.ValueType = ...,
    ) -> None: ...
    def ClearField(self, field_name: typing_extensions.Literal["status", b"status"]) -> None: ...

global___TopicEventResponse = TopicEventResponse

class TopicEventCERequest(google.protobuf.message.Message):
    """TopicEventCERequest message is compatible with CloudEvent spec v1.0"""

    DESCRIPTOR: google.protobuf.descriptor.Descriptor

    ID_FIELD_NUMBER: builtins.int
    SOURCE_FIELD_NUMBER: builtins.int
    TYPE_FIELD_NUMBER: builtins.int
    SPEC_VERSION_FIELD_NUMBER: builtins.int
    DATA_CONTENT_TYPE_FIELD_NUMBER: builtins.int
    DATA_FIELD_NUMBER: builtins.int
    EXTENSIONS_FIELD_NUMBER: builtins.int
    id: builtins.str
    """The unique identifier of this cloud event."""
    source: builtins.str
    """source identifies the context in which an event happened."""
    type: builtins.str
    """The type of event related to the originating occurrence."""
    spec_version: builtins.str
    """The version of the CloudEvents specification."""
    data_content_type: builtins.str
    """The content type of data value."""
    data: builtins.bytes
    """The content of the event."""
    @property
    def extensions(self) -> google.protobuf.struct_pb2.Struct:
        """Custom attributes which includes cloud event extensions."""
    def __init__(
        self,
        *,
        id: builtins.str = ...,
        source: builtins.str = ...,
        type: builtins.str = ...,
        spec_version: builtins.str = ...,
        data_content_type: builtins.str = ...,
        data: builtins.bytes = ...,
        extensions: google.protobuf.struct_pb2.Struct | None = ...,
    ) -> None: ...
    def HasField(self, field_name: typing_extensions.Literal["extensions", b"extensions"]) -> builtins.bool: ...
    def ClearField(self, field_name: typing_extensions.Literal["data", b"data", "data_content_type", b"data_content_type", "extensions", b"extensions", "id", b"id", "source", b"source", "spec_version", b"spec_version", "type", b"type"]) -> None: ...

global___TopicEventCERequest = TopicEventCERequest

class TopicEventBulkRequestEntry(google.protobuf.message.Message):
    """TopicEventBulkRequestEntry represents a single message inside a bulk request"""

    DESCRIPTOR: google.protobuf.descriptor.Descriptor

    class MetadataEntry(google.protobuf.message.Message):
        DESCRIPTOR: google.protobuf.descriptor.Descriptor

        KEY_FIELD_NUMBER: builtins.int
        VALUE_FIELD_NUMBER: builtins.int
        key: builtins.str
        value: builtins.str
        def __init__(
            self,
            *,
            key: builtins.str = ...,
            value: builtins.str = ...,
        ) -> None: ...
        def ClearField(self, field_name: typing_extensions.Literal["key", b"key", "value", b"value"]) -> None: ...

    ENTRY_ID_FIELD_NUMBER: builtins.int
    BYTES_FIELD_NUMBER: builtins.int
    CLOUD_EVENT_FIELD_NUMBER: builtins.int
    CONTENT_TYPE_FIELD_NUMBER: builtins.int
    METADATA_FIELD_NUMBER: builtins.int
    entry_id: builtins.str
    """Unique identifier for the message."""
    bytes: builtins.bytes
    @property
    def cloud_event(self) -> global___TopicEventCERequest: ...
    content_type: builtins.str
    """content type of the event contained."""
    @property
    def metadata(self) -> google.protobuf.internal.containers.ScalarMap[builtins.str, builtins.str]:
        """The metadata associated with the event."""
    def __init__(
        self,
        *,
        entry_id: builtins.str = ...,
        bytes: builtins.bytes = ...,
        cloud_event: global___TopicEventCERequest | None = ...,
        content_type: builtins.str = ...,
        metadata: collections.abc.Mapping[builtins.str, builtins.str] | None = ...,
    ) -> None: ...
    def HasField(self, field_name: typing_extensions.Literal["bytes", b"bytes", "cloud_event", b"cloud_event", "event", b"event"]) -> builtins.bool: ...
    def ClearField(self, field_name: typing_extensions.Literal["bytes", b"bytes", "cloud_event", b"cloud_event", "content_type", b"content_type", "entry_id", b"entry_id", "event", b"event", "metadata", b"metadata"]) -> None: ...
    def WhichOneof(self, oneof_group: typing_extensions.Literal["event", b"event"]) -> typing_extensions.Literal["bytes", "cloud_event"] | None: ...

global___TopicEventBulkRequestEntry = TopicEventBulkRequestEntry

class TopicEventBulkRequest(google.protobuf.message.Message):
    """TopicEventBulkRequest represents request for bulk message"""

    DESCRIPTOR: google.protobuf.descriptor.Descriptor

    class MetadataEntry(google.protobuf.message.Message):
        DESCRIPTOR: google.protobuf.descriptor.Descriptor

        KEY_FIELD_NUMBER: builtins.int
        VALUE_FIELD_NUMBER: builtins.int
        key: builtins.str
        value: builtins.str
        def __init__(
            self,
            *,
            key: builtins.str = ...,
            value: builtins.str = ...,
        ) -> None: ...
        def ClearField(self, field_name: typing_extensions.Literal["key", b"key", "value", b"value"]) -> None: ...

    ID_FIELD_NUMBER: builtins.int
    ENTRIES_FIELD_NUMBER: builtins.int
    METADATA_FIELD_NUMBER: builtins.int
    TOPIC_FIELD_NUMBER: builtins.int
    PUBSUB_NAME_FIELD_NUMBER: builtins.int
    TYPE_FIELD_NUMBER: builtins.int
    PATH_FIELD_NUMBER: builtins.int
    id: builtins.str
    """Unique identifier for the bulk request."""
    @property
    def entries(self) -> google.protobuf.internal.containers.RepeatedCompositeFieldContainer[global___TopicEventBulkRequestEntry]:
        """The list of items inside this bulk request."""
    @property
    def metadata(self) -> google.protobuf.internal.containers.ScalarMap[builtins.str, builtins.str]:
        """The metadata associated with the this bulk request."""
    topic: builtins.str
    """The pubsub topic which publisher sent to."""
    pubsub_name: builtins.str
    """The name of the pubsub the publisher sent to."""
    type: builtins.str
    """The type of event related to the originating occurrence."""
    path: builtins.str
    """The matching path from TopicSubscription/routes (if specified) for this event.
    This value is used by OnTopicEvent to "switch" inside the handler.
    """
    def __init__(
        self,
        *,
        id: builtins.str = ...,
        entries: collections.abc.Iterable[global___TopicEventBulkRequestEntry] | None = ...,
        metadata: collections.abc.Mapping[builtins.str, builtins.str] | None = ...,
        topic: builtins.str = ...,
        pubsub_name: builtins.str = ...,
        type: builtins.str = ...,
        path: builtins.str = ...,
    ) -> None: ...
    def ClearField(self, field_name: typing_extensions.Literal["entries", b"entries", "id", b"id", "metadata", b"metadata", "path", b"path", "pubsub_name", b"pubsub_name", "topic", b"topic", "type", b"type"]) -> None: ...

global___TopicEventBulkRequest = TopicEventBulkRequest

class TopicEventBulkResponseEntry(google.protobuf.message.Message):
    """TopicEventBulkResponseEntry Represents single response, as part of TopicEventBulkResponse, to be
    sent by subscibed App for the corresponding single message during bulk subscribe
    """

    DESCRIPTOR: google.protobuf.descriptor.Descriptor

    ENTRY_ID_FIELD_NUMBER: builtins.int
    STATUS_FIELD_NUMBER: builtins.int
    entry_id: builtins.str
    """Unique identifier associated the message."""
    status: global___TopicEventResponse.TopicEventResponseStatus.ValueType
    """The status of the response."""
    def __init__(
        self,
        *,
        entry_id: builtins.str = ...,
        status: global___TopicEventResponse.TopicEventResponseStatus.ValueType = ...,
    ) -> None: ...
    def ClearField(self, field_name: typing_extensions.Literal["entry_id", b"entry_id", "status", b"status"]) -> None: ...

global___TopicEventBulkResponseEntry = TopicEventBulkResponseEntry

class TopicEventBulkResponse(google.protobuf.message.Message):
    """AppBulkResponse is response from app on published message"""

    DESCRIPTOR: google.protobuf.descriptor.Descriptor

    STATUSES_FIELD_NUMBER: builtins.int
    @property
    def statuses(self) -> google.protobuf.internal.containers.RepeatedCompositeFieldContainer[global___TopicEventBulkResponseEntry]:
        """The list of all responses for the bulk request."""
    def __init__(
        self,
        *,
        statuses: collections.abc.Iterable[global___TopicEventBulkResponseEntry] | None = ...,
    ) -> None: ...
    def ClearField(self, field_name: typing_extensions.Literal["statuses", b"statuses"]) -> None: ...

global___TopicEventBulkResponse = TopicEventBulkResponse

class BindingEventRequest(google.protobuf.message.Message):
    """BindingEventRequest represents input bindings event."""

    DESCRIPTOR: google.protobuf.descriptor.Descriptor

    class MetadataEntry(google.protobuf.message.Message):
        DESCRIPTOR: google.protobuf.descriptor.Descriptor

        KEY_FIELD_NUMBER: builtins.int
        VALUE_FIELD_NUMBER: builtins.int
        key: builtins.str
        value: builtins.str
        def __init__(
            self,
            *,
            key: builtins.str = ...,
            value: builtins.str = ...,
        ) -> None: ...
        def ClearField(self, field_name: typing_extensions.Literal["key", b"key", "value", b"value"]) -> None: ...

    NAME_FIELD_NUMBER: builtins.int
    DATA_FIELD_NUMBER: builtins.int
    METADATA_FIELD_NUMBER: builtins.int
    name: builtins.str
    """Required. The name of the input binding component."""
    data: builtins.bytes
    """Required. The payload that the input bindings sent"""
    @property
    def metadata(self) -> google.protobuf.internal.containers.ScalarMap[builtins.str, builtins.str]:
        """The metadata set by the input binging components."""
    def __init__(
        self,
        *,
        name: builtins.str = ...,
        data: builtins.bytes = ...,
        metadata: collections.abc.Mapping[builtins.str, builtins.str] | None = ...,
    ) -> None: ...
    def ClearField(self, field_name: typing_extensions.Literal["data", b"data", "metadata", b"metadata", "name", b"name"]) -> None: ...

global___BindingEventRequest = BindingEventRequest

class BindingEventResponse(google.protobuf.message.Message):
    """BindingEventResponse includes operations to save state or
    send data to output bindings optionally.
    """

    DESCRIPTOR: google.protobuf.descriptor.Descriptor

    class _BindingEventConcurrency:
        ValueType = typing.NewType("ValueType", builtins.int)
        V: typing_extensions.TypeAlias = ValueType

    class _BindingEventConcurrencyEnumTypeWrapper(google.protobuf.internal.enum_type_wrapper._EnumTypeWrapper[BindingEventResponse._BindingEventConcurrency.ValueType], builtins.type):  # noqa: F821
        DESCRIPTOR: google.protobuf.descriptor.EnumDescriptor
        SEQUENTIAL: BindingEventResponse._BindingEventConcurrency.ValueType  # 0
        """SEQUENTIAL sends data to output bindings specified in "to" sequentially."""
        PARALLEL: BindingEventResponse._BindingEventConcurrency.ValueType  # 1
        """PARALLEL sends data to output bindings specified in "to" in parallel."""

    class BindingEventConcurrency(_BindingEventConcurrency, metaclass=_BindingEventConcurrencyEnumTypeWrapper):
        """BindingEventConcurrency is the kind of concurrency"""

    SEQUENTIAL: BindingEventResponse.BindingEventConcurrency.ValueType  # 0
    """SEQUENTIAL sends data to output bindings specified in "to" sequentially."""
    PARALLEL: BindingEventResponse.BindingEventConcurrency.ValueType  # 1
    """PARALLEL sends data to output bindings specified in "to" in parallel."""

    STORE_NAME_FIELD_NUMBER: builtins.int
    STATES_FIELD_NUMBER: builtins.int
    TO_FIELD_NUMBER: builtins.int
    DATA_FIELD_NUMBER: builtins.int
    CONCURRENCY_FIELD_NUMBER: builtins.int
    store_name: builtins.str
    """The name of state store where states are saved."""
    @property
    def states(self) -> google.protobuf.internal.containers.RepeatedCompositeFieldContainer[dapr.proto.common.v1.common_pb2.StateItem]:
        """The state key values which will be stored in store_name."""
    @property
    def to(self) -> google.protobuf.internal.containers.RepeatedScalarFieldContainer[builtins.str]:
        """The list of output bindings."""
    data: builtins.bytes
    """The content which will be sent to "to" output bindings."""
    concurrency: global___BindingEventResponse.BindingEventConcurrency.ValueType
    """The concurrency of output bindings to send data to
    "to" output bindings list. The default is SEQUENTIAL.
    """
    def __init__(
        self,
        *,
        store_name: builtins.str = ...,
        states: collections.abc.Iterable[dapr.proto.common.v1.common_pb2.StateItem] | None = ...,
        to: collections.abc.Iterable[builtins.str] | None = ...,
        data: builtins.bytes = ...,
        concurrency: global___BindingEventResponse.BindingEventConcurrency.ValueType = ...,
    ) -> None: ...
    def ClearField(self, field_name: typing_extensions.Literal["concurrency", b"concurrency", "data", b"data", "states", b"states", "store_name", b"store_name", "to", b"to"]) -> None: ...

global___BindingEventResponse = BindingEventResponse

class ListTopicSubscriptionsResponse(google.protobuf.message.Message):
    """ListTopicSubscriptionsResponse is the message including the list of the subscribing topics."""

    DESCRIPTOR: google.protobuf.descriptor.Descriptor

    SUBSCRIPTIONS_FIELD_NUMBER: builtins.int
    @property
    def subscriptions(self) -> google.protobuf.internal.containers.RepeatedCompositeFieldContainer[global___TopicSubscription]:
        """The list of topics."""
    def __init__(
        self,
        *,
        subscriptions: collections.abc.Iterable[global___TopicSubscription] | None = ...,
    ) -> None: ...
    def ClearField(self, field_name: typing_extensions.Literal["subscriptions", b"subscriptions"]) -> None: ...

global___ListTopicSubscriptionsResponse = ListTopicSubscriptionsResponse

class TopicSubscription(google.protobuf.message.Message):
    """TopicSubscription represents topic and metadata."""

    DESCRIPTOR: google.protobuf.descriptor.Descriptor

    class MetadataEntry(google.protobuf.message.Message):
        DESCRIPTOR: google.protobuf.descriptor.Descriptor

        KEY_FIELD_NUMBER: builtins.int
        VALUE_FIELD_NUMBER: builtins.int
        key: builtins.str
        value: builtins.str
        def __init__(
            self,
            *,
            key: builtins.str = ...,
            value: builtins.str = ...,
        ) -> None: ...
        def ClearField(self, field_name: typing_extensions.Literal["key", b"key", "value", b"value"]) -> None: ...

    PUBSUB_NAME_FIELD_NUMBER: builtins.int
    TOPIC_FIELD_NUMBER: builtins.int
    METADATA_FIELD_NUMBER: builtins.int
    ROUTES_FIELD_NUMBER: builtins.int
    DEAD_LETTER_TOPIC_FIELD_NUMBER: builtins.int
    pubsub_name: builtins.str
    """Required. The name of the pubsub containing the topic below to subscribe to."""
    topic: builtins.str
    """Required. The name of topic which will be subscribed"""
    @property
    def metadata(self) -> google.protobuf.internal.containers.ScalarMap[builtins.str, builtins.str]:
        """The optional properties used for this topic's subscription e.g. session id"""
    @property
    def routes(self) -> global___TopicRoutes:
        """The optional routing rules to match against. In the gRPC interface, OnTopicEvent
        is still invoked but the matching path is sent in the TopicEventRequest.
        """
    dead_letter_topic: builtins.str
    """The optional dead letter queue for this topic to send events to."""
    def __init__(
        self,
        *,
        pubsub_name: builtins.str = ...,
        topic: builtins.str = ...,
        metadata: collections.abc.Mapping[builtins.str, builtins.str] | None = ...,
        routes: global___TopicRoutes | None = ...,
        dead_letter_topic: builtins.str = ...,
    ) -> None: ...
    def HasField(self, field_name: typing_extensions.Literal["routes", b"routes"]) -> builtins.bool: ...
    def ClearField(self, field_name: typing_extensions.Literal["dead_letter_topic", b"dead_letter_topic", "metadata", b"metadata", "pubsub_name", b"pubsub_name", "routes", b"routes", "topic", b"topic"]) -> None: ...

global___TopicSubscription = TopicSubscription

class TopicRoutes(google.protobuf.message.Message):
    DESCRIPTOR: google.protobuf.descriptor.Descriptor

    RULES_FIELD_NUMBER: builtins.int
    DEFAULT_FIELD_NUMBER: builtins.int
    @property
    def rules(self) -> google.protobuf.internal.containers.RepeatedCompositeFieldContainer[global___TopicRule]:
        """The list of rules for this topic."""
    default: builtins.str
    """The default path for this topic."""
    def __init__(
        self,
        *,
        rules: collections.abc.Iterable[global___TopicRule] | None = ...,
        default: builtins.str = ...,
    ) -> None: ...
    def ClearField(self, field_name: typing_extensions.Literal["default", b"default", "rules", b"rules"]) -> None: ...

global___TopicRoutes = TopicRoutes

class TopicRule(google.protobuf.message.Message):
    DESCRIPTOR: google.protobuf.descriptor.Descriptor

    MATCH_FIELD_NUMBER: builtins.int
    PATH_FIELD_NUMBER: builtins.int
    match: builtins.str
    """The optional CEL expression used to match the event.
    If the match is not specified, then the route is considered
    the default.
    """
    path: builtins.str
    """The path used to identify matches for this subscription.
    This value is passed in TopicEventRequest and used by OnTopicEvent to "switch"
    inside the handler.
    """
    def __init__(
        self,
        *,
        match: builtins.str = ...,
        path: builtins.str = ...,
    ) -> None: ...
    def ClearField(self, field_name: typing_extensions.Literal["match", b"match", "path", b"path"]) -> None: ...

global___TopicRule = TopicRule

class ListInputBindingsResponse(google.protobuf.message.Message):
    """ListInputBindingsResponse is the message including the list of input bindings."""

    DESCRIPTOR: google.protobuf.descriptor.Descriptor

    BINDINGS_FIELD_NUMBER: builtins.int
    @property
    def bindings(self) -> google.protobuf.internal.containers.RepeatedScalarFieldContainer[builtins.str]:
        """The list of input bindings."""
    def __init__(
        self,
        *,
        bindings: collections.abc.Iterable[builtins.str] | None = ...,
    ) -> None: ...
    def ClearField(self, field_name: typing_extensions.Literal["bindings", b"bindings"]) -> None: ...

global___ListInputBindingsResponse = ListInputBindingsResponse

class HealthCheckResponse(google.protobuf.message.Message):
    """HealthCheckResponse is the message with the response to the health check.
    This message is currently empty as used as placeholder.
    """

    DESCRIPTOR: google.protobuf.descriptor.Descriptor

    def __init__(
        self,
    ) -> None: ...

global___HealthCheckResponse = HealthCheckResponse
