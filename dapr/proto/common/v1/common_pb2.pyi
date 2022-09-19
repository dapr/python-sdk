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
import google.protobuf.any_pb2
import google.protobuf.descriptor
import google.protobuf.internal.containers
import google.protobuf.internal.enum_type_wrapper
import google.protobuf.message
import sys
import typing

if sys.version_info >= (3, 10):
    import typing as typing_extensions
else:
    import typing_extensions

DESCRIPTOR: google.protobuf.descriptor.FileDescriptor

class HTTPExtension(google.protobuf.message.Message):
    """HTTPExtension includes HTTP verb and querystring
    when Dapr runtime delivers HTTP content.

    For example, when callers calls http invoke api
    POST http://localhost:3500/v1.0/invoke/<app_id>/method/<method>?query1=value1&query2=value2

    Dapr runtime will parse POST as a verb and extract querystring to quersytring map.
    """

    DESCRIPTOR: google.protobuf.descriptor.Descriptor

    class _Verb:
        ValueType = typing.NewType("ValueType", builtins.int)
        V: typing_extensions.TypeAlias = ValueType

    class _VerbEnumTypeWrapper(google.protobuf.internal.enum_type_wrapper._EnumTypeWrapper[HTTPExtension._Verb.ValueType], builtins.type):  # noqa: F821
        DESCRIPTOR: google.protobuf.descriptor.EnumDescriptor
        NONE: HTTPExtension._Verb.ValueType  # 0
        GET: HTTPExtension._Verb.ValueType  # 1
        HEAD: HTTPExtension._Verb.ValueType  # 2
        POST: HTTPExtension._Verb.ValueType  # 3
        PUT: HTTPExtension._Verb.ValueType  # 4
        DELETE: HTTPExtension._Verb.ValueType  # 5
        CONNECT: HTTPExtension._Verb.ValueType  # 6
        OPTIONS: HTTPExtension._Verb.ValueType  # 7
        TRACE: HTTPExtension._Verb.ValueType  # 8
        PATCH: HTTPExtension._Verb.ValueType  # 9

    class Verb(_Verb, metaclass=_VerbEnumTypeWrapper):
        """Type of HTTP 1.1 Methods
        RFC 7231: https://tools.ietf.org/html/rfc7231#page-24
        RFC 5789: https://datatracker.ietf.org/doc/html/rfc5789
        """

    NONE: HTTPExtension.Verb.ValueType  # 0
    GET: HTTPExtension.Verb.ValueType  # 1
    HEAD: HTTPExtension.Verb.ValueType  # 2
    POST: HTTPExtension.Verb.ValueType  # 3
    PUT: HTTPExtension.Verb.ValueType  # 4
    DELETE: HTTPExtension.Verb.ValueType  # 5
    CONNECT: HTTPExtension.Verb.ValueType  # 6
    OPTIONS: HTTPExtension.Verb.ValueType  # 7
    TRACE: HTTPExtension.Verb.ValueType  # 8
    PATCH: HTTPExtension.Verb.ValueType  # 9

    VERB_FIELD_NUMBER: builtins.int
    QUERYSTRING_FIELD_NUMBER: builtins.int
    verb: global___HTTPExtension.Verb.ValueType
    """Required. HTTP verb."""
    querystring: builtins.str
    """Optional. querystring represents an encoded HTTP url query string in the following format: name=value&name2=value2"""
    def __init__(
        self,
        *,
        verb: global___HTTPExtension.Verb.ValueType = ...,
        querystring: builtins.str = ...,
    ) -> None: ...
    def ClearField(self, field_name: typing_extensions.Literal["querystring", b"querystring", "verb", b"verb"]) -> None: ...

global___HTTPExtension = HTTPExtension

class InvokeRequest(google.protobuf.message.Message):
    """InvokeRequest is the message to invoke a method with the data.
    This message is used in InvokeService of Dapr gRPC Service and OnInvoke
    of AppCallback gRPC service.
    """

    DESCRIPTOR: google.protobuf.descriptor.Descriptor

    METHOD_FIELD_NUMBER: builtins.int
    DATA_FIELD_NUMBER: builtins.int
    CONTENT_TYPE_FIELD_NUMBER: builtins.int
    HTTP_EXTENSION_FIELD_NUMBER: builtins.int
    method: builtins.str
    """Required. method is a method name which will be invoked by caller."""
    @property
    def data(self) -> google.protobuf.any_pb2.Any:
        """Required. Bytes value or Protobuf message which caller sent.
        Dapr treats Any.value as bytes type if Any.type_url is unset.
        """
    content_type: builtins.str
    """The type of data content.

    This field is required if data delivers http request body
    Otherwise, this is optional.
    """
    @property
    def http_extension(self) -> global___HTTPExtension:
        """HTTP specific fields if request conveys http-compatible request.

        This field is required for http-compatible request. Otherwise,
        this field is optional.
        """
    def __init__(
        self,
        *,
        method: builtins.str = ...,
        data: google.protobuf.any_pb2.Any | None = ...,
        content_type: builtins.str = ...,
        http_extension: global___HTTPExtension | None = ...,
    ) -> None: ...
    def HasField(self, field_name: typing_extensions.Literal["data", b"data", "http_extension", b"http_extension"]) -> builtins.bool: ...
    def ClearField(self, field_name: typing_extensions.Literal["content_type", b"content_type", "data", b"data", "http_extension", b"http_extension", "method", b"method"]) -> None: ...

global___InvokeRequest = InvokeRequest

class InvokeResponse(google.protobuf.message.Message):
    """InvokeResponse is the response message inclduing data and its content type
    from app callback.
    This message is used in InvokeService of Dapr gRPC Service and OnInvoke
    of AppCallback gRPC service.
    """

    DESCRIPTOR: google.protobuf.descriptor.Descriptor

    DATA_FIELD_NUMBER: builtins.int
    CONTENT_TYPE_FIELD_NUMBER: builtins.int
    @property
    def data(self) -> google.protobuf.any_pb2.Any:
        """Required. The content body of InvokeService response."""
    content_type: builtins.str
    """Required. The type of data content."""
    def __init__(
        self,
        *,
        data: google.protobuf.any_pb2.Any | None = ...,
        content_type: builtins.str = ...,
    ) -> None: ...
    def HasField(self, field_name: typing_extensions.Literal["data", b"data"]) -> builtins.bool: ...
    def ClearField(self, field_name: typing_extensions.Literal["content_type", b"content_type", "data", b"data"]) -> None: ...

global___InvokeResponse = InvokeResponse

class StateItem(google.protobuf.message.Message):
    """StateItem represents state key, value, and additional options to save state."""

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

    KEY_FIELD_NUMBER: builtins.int
    VALUE_FIELD_NUMBER: builtins.int
    ETAG_FIELD_NUMBER: builtins.int
    METADATA_FIELD_NUMBER: builtins.int
    OPTIONS_FIELD_NUMBER: builtins.int
    key: builtins.str
    """Required. The state key"""
    value: builtins.bytes
    """Required. The state data for key"""
    @property
    def etag(self) -> global___Etag:
        """The entity tag which represents the specific version of data.
        The exact ETag format is defined by the corresponding data store.
        """
    @property
    def metadata(self) -> google.protobuf.internal.containers.ScalarMap[builtins.str, builtins.str]:
        """The metadata which will be passed to state store component."""
    @property
    def options(self) -> global___StateOptions:
        """Options for concurrency and consistency to save the state."""
    def __init__(
        self,
        *,
        key: builtins.str = ...,
        value: builtins.bytes = ...,
        etag: global___Etag | None = ...,
        metadata: collections.abc.Mapping[builtins.str, builtins.str] | None = ...,
        options: global___StateOptions | None = ...,
    ) -> None: ...
    def HasField(self, field_name: typing_extensions.Literal["etag", b"etag", "options", b"options"]) -> builtins.bool: ...
    def ClearField(self, field_name: typing_extensions.Literal["etag", b"etag", "key", b"key", "metadata", b"metadata", "options", b"options", "value", b"value"]) -> None: ...

global___StateItem = StateItem

class Etag(google.protobuf.message.Message):
    """Etag represents a state item version"""

    DESCRIPTOR: google.protobuf.descriptor.Descriptor

    VALUE_FIELD_NUMBER: builtins.int
    value: builtins.str
    """value sets the etag value"""
    def __init__(
        self,
        *,
        value: builtins.str = ...,
    ) -> None: ...
    def ClearField(self, field_name: typing_extensions.Literal["value", b"value"]) -> None: ...

global___Etag = Etag

class StateOptions(google.protobuf.message.Message):
    """StateOptions configures concurrency and consistency for state operations"""

    DESCRIPTOR: google.protobuf.descriptor.Descriptor

    class _StateConcurrency:
        ValueType = typing.NewType("ValueType", builtins.int)
        V: typing_extensions.TypeAlias = ValueType

    class _StateConcurrencyEnumTypeWrapper(google.protobuf.internal.enum_type_wrapper._EnumTypeWrapper[StateOptions._StateConcurrency.ValueType], builtins.type):  # noqa: F821
        DESCRIPTOR: google.protobuf.descriptor.EnumDescriptor
        CONCURRENCY_UNSPECIFIED: StateOptions._StateConcurrency.ValueType  # 0
        CONCURRENCY_FIRST_WRITE: StateOptions._StateConcurrency.ValueType  # 1
        CONCURRENCY_LAST_WRITE: StateOptions._StateConcurrency.ValueType  # 2

    class StateConcurrency(_StateConcurrency, metaclass=_StateConcurrencyEnumTypeWrapper):
        """Enum describing the supported concurrency for state."""

    CONCURRENCY_UNSPECIFIED: StateOptions.StateConcurrency.ValueType  # 0
    CONCURRENCY_FIRST_WRITE: StateOptions.StateConcurrency.ValueType  # 1
    CONCURRENCY_LAST_WRITE: StateOptions.StateConcurrency.ValueType  # 2

    class _StateConsistency:
        ValueType = typing.NewType("ValueType", builtins.int)
        V: typing_extensions.TypeAlias = ValueType

    class _StateConsistencyEnumTypeWrapper(google.protobuf.internal.enum_type_wrapper._EnumTypeWrapper[StateOptions._StateConsistency.ValueType], builtins.type):  # noqa: F821
        DESCRIPTOR: google.protobuf.descriptor.EnumDescriptor
        CONSISTENCY_UNSPECIFIED: StateOptions._StateConsistency.ValueType  # 0
        CONSISTENCY_EVENTUAL: StateOptions._StateConsistency.ValueType  # 1
        CONSISTENCY_STRONG: StateOptions._StateConsistency.ValueType  # 2

    class StateConsistency(_StateConsistency, metaclass=_StateConsistencyEnumTypeWrapper):
        """Enum describing the supported consistency for state."""

    CONSISTENCY_UNSPECIFIED: StateOptions.StateConsistency.ValueType  # 0
    CONSISTENCY_EVENTUAL: StateOptions.StateConsistency.ValueType  # 1
    CONSISTENCY_STRONG: StateOptions.StateConsistency.ValueType  # 2

    CONCURRENCY_FIELD_NUMBER: builtins.int
    CONSISTENCY_FIELD_NUMBER: builtins.int
    concurrency: global___StateOptions.StateConcurrency.ValueType
    consistency: global___StateOptions.StateConsistency.ValueType
    def __init__(
        self,
        *,
        concurrency: global___StateOptions.StateConcurrency.ValueType = ...,
        consistency: global___StateOptions.StateConsistency.ValueType = ...,
    ) -> None: ...
    def ClearField(self, field_name: typing_extensions.Literal["concurrency", b"concurrency", "consistency", b"consistency"]) -> None: ...

global___StateOptions = StateOptions

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

class ConfigurationItem(google.protobuf.message.Message):
    """ConfigurationItem represents all the configuration with its name(key)."""

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

    VALUE_FIELD_NUMBER: builtins.int
    VERSION_FIELD_NUMBER: builtins.int
    METADATA_FIELD_NUMBER: builtins.int
    value: builtins.str
    """Required. The value of configuration item."""
    version: builtins.str
    """Version is response only and cannot be fetched. Store is not expected to keep all versions available"""
    @property
    def metadata(self) -> google.protobuf.internal.containers.ScalarMap[builtins.str, builtins.str]:
        """the metadata which will be passed to/from configuration store component."""
    def __init__(
        self,
        *,
        value: builtins.str = ...,
        version: builtins.str = ...,
        metadata: collections.abc.Mapping[builtins.str, builtins.str] | None = ...,
    ) -> None: ...
    def ClearField(self, field_name: typing_extensions.Literal["metadata", b"metadata", "value", b"value", "version", b"version"]) -> None: ...

global___ConfigurationItem = ConfigurationItem
