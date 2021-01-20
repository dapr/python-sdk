# -*- coding: utf-8 -*-

"""
Copyright (c) Microsoft Corporation.
Licensed under the MIT License.
"""
import grpc

from cloudevents.sdk.event import v1  # type: ignore
from typing import Callable, Dict, List, Optional, Union

from google.protobuf import empty_pb2
from google.protobuf.message import Message as GrpcMessage

from dapr.proto import appcallback_service_v1, common_v1, appcallback_v1
from dapr.clients.base import DEFAULT_JSON_CONTENT_TYPE
from dapr.clients.grpc._request import InvokeMethodRequest, BindingRequest
from dapr.clients.grpc._response import InvokeMethodResponse


InvokeMethodCallable = Callable[[InvokeMethodRequest], Union[str, bytes, InvokeMethodResponse]]
TopicSubscribeCallable = Callable[[v1.Event], None]
BindingCallable = Callable[[BindingRequest], None]

DELIMITER = ":"


class _CallbackServicer(appcallback_service_v1.AppCallbackServicer):
    """The implementation of AppCallback Server.

    This internal class implements application server and provides helpers to register
    method, topic, and input bindings. It implements the routing handling logic to route
    mulitple methods, topics, and bindings.

    :class:`App` provides useful decorators to register method, topic, input bindings.
    """
    def __init__(self):
        self._invoke_method_map: Dict[str, InvokeMethodCallable] = {}
        self._topic_map: Dict[str, TopicSubscribeCallable] = {}
        self._binding_map: Dict[str, BindingCallable] = {}

        self._registered_topics: List[str] = []
        self._registered_bindings: List[str] = []

    def register_method(self, method: str, cb: InvokeMethodCallable) -> None:
        """Registers method for service invocation."""
        if method in self._invoke_method_map:
            raise ValueError(f'{method} is already registered')
        self._invoke_method_map[method] = cb

    def register_topic(
            self,
            pubsub_name: str,
            topic: str,
            cb: TopicSubscribeCallable,
            metadata: Optional[Dict[str, str]]) -> None:
        """Registers topic subscription for pubsub."""
        pubsub_topic = pubsub_name + DELIMITER + topic
        if pubsub_topic in self._topic_map:
            raise ValueError(f'{topic} is already registered with {pubsub_name}')
        self._topic_map[pubsub_topic] = cb
        self._registered_topics.append(
            appcallback_v1.TopicSubscription(
                pubsub_name=pubsub_name,
                topic=topic,
                metadata=metadata
            )
        )

    def register_binding(
            self, name: str, cb: BindingCallable) -> None:
        """Registers input bindings."""
        if name in self._binding_map:
            raise ValueError(f'{name} is already registered')
        self._binding_map[name] = cb
        self._registered_bindings.append(name)

    def OnInvoke(self, request, context):
        """Invokes service method with InvokeRequest."""
        if request.method not in self._invoke_method_map:
            context.set_code(grpc.StatusCode.UNIMPLEMENTED)  # type: ignore
            raise NotImplementedError(f'{request.method} method not implemented!')

        req = InvokeMethodRequest(request.data, request.content_type)
        req.metadata = context.invocation_metadata()
        resp = self._invoke_method_map[request.method](req)

        if not resp:
            return common_v1.InvokeResponse()

        resp_data = InvokeMethodResponse()
        if isinstance(resp, (bytes, str)):
            resp_data.set_data(resp)
            resp_data.content_type = DEFAULT_JSON_CONTENT_TYPE
        elif isinstance(resp, GrpcMessage):
            resp_data.set_data(resp)
        elif isinstance(resp, InvokeMethodResponse):
            resp_data = resp
        else:
            context.set_code(grpc.StatusCode.OUT_OF_RANGE)
            context.set_details(f'{type(resp)} is the invalid return type.')
            raise NotImplementedError(f'{request.method} method not implemented!')

        if len(resp_data.get_headers()) > 0:
            context.send_initial_metadata(resp_data.get_headers())

        return common_v1.InvokeResponse(
            data=resp_data.proto, content_type=resp_data.content_type)

    def ListTopicSubscriptions(self, request, context):
        """Lists all topics subscribed by this app."""
        return appcallback_v1.ListTopicSubscriptionsResponse(
            subscriptions=self._registered_topics)

    def OnTopicEvent(self, request, context):
        """Subscribes events from Pubsub."""
        pubsub_topic = request.pubsub_name + DELIMITER + request.topic
        if pubsub_topic not in self._topic_map:
            context.set_code(grpc.StatusCode.UNIMPLEMENTED)  # type: ignore
            raise NotImplementedError(f'topic {request.topic} is not implemented!')

        event = v1.Event()
        event.SetEventType(request.type)
        event.SetEventID(request.id)
        event.SetSource(request.source)
        event.SetData(request.data)
        event.SetContentType(request.data_content_type)

        # TODO: add metadata from context to CE envelope

        self._topic_map[pubsub_topic](event)

        return empty_pb2.Empty()

    def ListInputBindings(self, request, context):
        """Lists all input bindings subscribed by this app."""
        return appcallback_v1.ListInputBindingsResponse(
            bindings=self._registered_bindings)

    def OnBindingEvent(self, request, context):
        """Listens events from the input bindings
        User application can save the states or send the events to the output
        bindings optionally by returning BindingEventResponse.
        """
        if request.name not in self._binding_map:
            context.set_code(grpc.StatusCode.UNIMPLEMENTED)   # type: ignore
            raise NotImplementedError(f'{request.name} binding not implemented!')

        req = BindingRequest(request.data, request.metadata)
        req.metadata = context.invocation_metadata()
        self._binding_map[request.name](req)

        # TODO: support output bindings options
        return appcallback_v1.BindingEventResponse()
