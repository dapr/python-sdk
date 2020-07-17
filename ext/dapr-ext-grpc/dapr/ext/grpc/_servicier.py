# -*- coding: utf-8 -*-

"""
Copyright (c) Microsoft Corporation.
Licensed under the MIT License.
"""
import grpc

from cloudevents.sdk.event import v1
from typing import Callable, Dict, Optional

from google.protobuf import empty_pb2
from google.protobuf.message import Message as GrpcMessage

from dapr.proto import appcallback_service_v1, common_v1, appcallback_v1
from dapr.clients.base import DEFAULT_JSON_CONTENT_TYPE
from dapr.clients.grpc._request import InvokeServiceRequest
from dapr.clients.grpc._response import InvokeServiceResponse

from dapr.ext.grpc.request import InputBindingRequest


InvokeMethodCallback = Callable[[InvokeServiceRequest], InvokeServiceResponse]
SubscriberCallback = Callable[[v1.Event], None]
BindingCallback = Callable[[InputBindingRequest], None]


class AppCallbackServicer(appcallback_service_v1.AppCallbackServicer):
    def __init__(self):
        self._invoke_method_map: Dict[str, InvokeMethodCallback] = {}
        self._subscription_map: Dict[str, SubscriberCallback] = {}
        self._binding_map: Dict[str, BindingCallback] = {}

        self._registered_topics = []
        self._registered_bindings = []

    def register_method(self, method: str, cb: InvokeMethodCallback) -> None:
        if method in self._invoke_method_map:
            raise ValueError(f'{method} is already registered')
        self._invoke_method_map[method] = cb

    def register_subscribe(
            self, topic: str,
            cb: SubscriberCallback, metadata: Optional[Dict[str, str]]) -> None:
        if topic in self._subscription_map:
            raise ValueError(f'{topic} is already registered')
        self._subscription_map[topic] = cb
        self._registered_topics.append(
            appcallback_v1.TopicSubscription(topic=topic, metadata=metadata))

    def register_binding(
            self, name: str, cb: BindingCallback) -> None:
        if name in self._binding_map:
            raise ValueError(f'{name} is already registered')
        self._binding_map[name] = cb
        self._registered_bindings.append(name)

    def OnInvoke(
            self,
            request: common_v1.InvokeRequest,
            context) -> common_v1.InvokeResponse:
        """Invokes service method with InvokeRequest.
        """
        if request.method not in self._invoke_method_map:
            context.set_code(grpc.StatusCode.UNIMPLEMENTED)
            raise NotImplementedError(f'{request.method} method not implemented!')

        req = InvokeServiceRequest(request.data, request.content_type)
        resp = self._invoke_method_map[request.method](req)

        if not resp:
            return common_v1.InvokeResponse()

        resp_data = InvokeServiceResponse()
        if isinstance(resp, (bytes, str)):
            resp_data.data = resp
            resp_data.content_type = DEFAULT_JSON_CONTENT_TYPE
        elif isinstance(resp, GrpcMessage):
            resp_data.data = resp
        elif not isinstance(resp, InvokeServiceResponse):
            context.set_code(grpc.StatusCode.OUT_OF_RANGE)
            context.set_details(f'{type(resp)} is the invalid return type.')
            raise NotImplementedError(f'{request.name} binding not implemented!')

        if len(resp_data.get_headers()) > 0:
            context.send_initial_metadata(resp_data.get_headers())

        return common_v1.InvokeResponse(
            data=resp_data.proto, content_type=resp_data.content_type)

    def ListTopicSubscriptions(
            self, request, context) -> appcallback_v1.ListTopicSubscriptionsResponse:
        """Lists all topics subscribed by this app."""
        return appcallback_v1.ListTopicSubscriptionsResponse(
            subscriptions=self._registered_topics)

    def OnTopicEvent(
            self,
            request: appcallback_v1.TopicEventRequest,
            context) -> None:
        """Subscribes events from Pubsub."""
        if request.topic not in self._subscription_map:
            context.set_code(grpc.StatusCode.UNIMPLEMENTED)
            raise NotImplementedError(f'topic {request.topic} is not implemented!')

        event = v1.Event()
        event.SetEventType(request.type)
        event.SetEventID(request.id)
        event.SetSource(request.source)
        event.SetData(request.data)
        event.SetContentType(request.data_content_type)

        self._subscription_map[request.topic](event)

        return empty_pb2.Empty()
        

    def ListInputBindings(
            self, request, context) -> appcallback_v1.ListInputBindingsResponse:
        """Lists all input bindings subscribed by this app."""
        return appcallback_v1.ListInputBindingsResponse(
            bindings=self._registered_bindings)

    def OnBindingEvent(
            self,
            request: appcallback_v1.BindingEventRequest,
            context) -> appcallback_v1.BindingEventResponse:
        """Listens events from the input bindings
        User application can save the states or send the events to the output
        bindings optionally by returning BindingEventResponse.
        """
        if request.name not in self._binding_map:
            context.set_code(grpc.StatusCode.UNIMPLEMENTED)
            raise NotImplementedError(f'{request.name} binding not implemented!')

        self._binding_map[request.name](InputBindingRequest(request.metadata, request.data))

        # TODO: support output bindings options
        return appcallback_v1.BindingEventResponse()
