# -*- coding: utf-8 -*-

"""
Copyright 2023 The Dapr Authors
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

import warnings
from typing import Any, Callable, Dict, List, Optional, Protocol, Tuple, Union

import grpc
from cloudevents.sdk.event import v1  # type: ignore
from google.protobuf import empty_pb2
from google.protobuf.message import Message as GrpcMessage
from google.protobuf.struct_pb2 import Struct

from dapr.clients._constants import DEFAULT_JSON_CONTENT_TYPE
from dapr.clients.grpc._request import BindingRequest, InvokeMethodRequest, JobEvent
from dapr.clients.grpc._response import InvokeMethodResponse, TopicEventResponse
from dapr.common.pubsub.subscription import SubscriptionMessage
from dapr.proto import appcallback_service_v1, appcallback_v1, common_v1
from dapr.proto.common.v1.common_pb2 import InvokeRequest
from dapr.proto.runtime.v1.appcallback_pb2 import (
    BindingEventRequest,
    JobEventRequest,
    TopicEventBulkRequest,
    TopicEventBulkRequestEntry,
    TopicEventBulkResponse,
    TopicEventRequest,
)

InvokeMethodCallable = Callable[[InvokeMethodRequest], Union[str, bytes, InvokeMethodResponse]]
TopicSubscribeCallable = Callable[
    [Union[v1.Event, SubscriptionMessage]], Optional[TopicEventResponse]
]
BindingCallable = Callable[[BindingRequest], None]
JobEventCallable = Callable[[JobEvent], None]

DELIMITER = ':'

HandlerResponse = Union[str, bytes, GrpcMessage, InvokeMethodResponse]


class _ServicerContext(Protocol):
    """The subset of the gRPC servicer context the shared helpers rely on.

    Declared structurally because the synchronous and asyncio servicers are handed a
    ``grpc.ServicerContext`` and a ``grpc.aio.ServicerContext`` respectively, which share no
    common base class but expose these members identically.
    """

    def set_code(self, code: grpc.StatusCode) -> None: ...

    def set_details(self, details: str) -> None: ...

    def invocation_metadata(self) -> Any: ...


class Rule:
    def __init__(self, match: str, priority: int) -> None:
        self.match = match
        self.priority = priority


class _RegisteredSubscription:
    def __init__(
        self,
        subscription: appcallback_v1.TopicSubscription,
        rules: List[Tuple[int, appcallback_v1.TopicRule]],
    ):
        self.subscription = subscription
        self.rules = rules


class _CallbackServicerBase(
    appcallback_service_v1.AppCallbackServicer, appcallback_service_v1.AppCallbackAlphaServicer
):
    """Handler registration and request translation shared by the sync and asyncio servicers.

    Holds every part of the AppCallback implementation that does not invoke a user handler:
    the handler registries, the topic routing table, and the translation of incoming gRPC
    requests into the SDK types handlers receive. :class:`_CallbackServicer` and
    :class:`dapr.ext.grpc.aio._servicer._AioCallbackServicer` add the gRPC entry points on
    top, which differ only in whether they await the handler.
    """

    def __init__(self):
        self._invoke_method_map: Dict[str, InvokeMethodCallable] = {}
        self._topic_map: Dict[str, TopicSubscribeCallable] = {}
        self._topic_legacy_event: Dict[TopicSubscribeCallable, bool] = {}
        self._binding_map: Dict[str, BindingCallable] = {}
        self._job_event_map: Dict[str, JobEventCallable] = {}

        self._registered_topics_map: Dict[str, _RegisteredSubscription] = {}
        self._registered_topics: List[appcallback_v1.TopicSubscription] = []
        self._registered_bindings: List[str] = []

        self._route_map: Dict[Tuple[str, str], TopicSubscribeCallable] = {}
        self._validation_disabled_pubsubs: Dict[str, List[TopicSubscribeCallable]] = {}

    def _get_topic_callback(
        self, pubsub_name: str, topic: str, path: str
    ) -> Optional[TopicSubscribeCallable]:
        pubsub_topic = pubsub_name + DELIMITER + topic + DELIMITER + path
        if pubsub_topic in self._topic_map:
            return self._topic_map[pubsub_topic]

        if (pubsub_name, path) in self._route_map:
            return self._route_map[(pubsub_name, path)]

        if path == '':
            if (pubsub_name, topic) in self._route_map:
                return self._route_map[(pubsub_name, topic)]

            if pubsub_name in self._validation_disabled_pubsubs:
                callbacks = self._validation_disabled_pubsubs[pubsub_name]
                if len(callbacks) == 1:
                    return callbacks[0]

        return None

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
        metadata: Optional[Dict[str, str]],
        dead_letter_topic: Optional[str] = None,
        rule: Optional[Rule] = None,
        disable_topic_validation: Optional[bool] = False,
        legacy_cloudevent: bool = True,
    ) -> None:
        """Registers topic subscription for pubsub.

        Args:
            legacy_cloudevent (bool): when True (deprecated default), the handler receives a
                ``cloudevents.sdk.event.v1.Event``; when False, it receives a
                :class:`dapr.common.pubsub.subscription.SubscriptionMessage`.
        """
        topic_key = pubsub_name + DELIMITER + topic
        pubsub_topic = topic_key + DELIMITER
        if rule is not None:
            path = getattr(cb, '__name__', rule.match)
            pubsub_topic = pubsub_topic + path
        if pubsub_topic in self._topic_map:
            raise ValueError(f'{topic} is already registered with {pubsub_name}')
        self._topic_map[pubsub_topic] = cb
        self._topic_legacy_event[cb] = legacy_cloudevent
        routing_path = path if rule is not None else topic
        self._route_map[(pubsub_name, routing_path)] = cb

        if disable_topic_validation:
            if pubsub_name not in self._validation_disabled_pubsubs:
                self._validation_disabled_pubsubs[pubsub_name] = []
            self._validation_disabled_pubsubs[pubsub_name].append(cb)

        registered_topic = self._registered_topics_map.get(topic_key)
        sub: appcallback_v1.TopicSubscription = appcallback_v1.TopicSubscription()
        rules: List[Tuple[int, appcallback_v1.TopicRule]] = []
        if not registered_topic:
            sub = appcallback_v1.TopicSubscription(
                pubsub_name=pubsub_name,
                topic=topic,
                metadata=metadata,
                routes=appcallback_v1.TopicRoutes(),
            )
            if dead_letter_topic:
                sub.dead_letter_topic = dead_letter_topic

            if disable_topic_validation and rule is None:
                sub.routes.default = topic

            registered_topic = _RegisteredSubscription(sub, rules)
            self._registered_topics_map[topic_key] = registered_topic
            self._registered_topics.append(sub)

        sub = registered_topic.subscription
        rules = registered_topic.rules

        if rule:
            path = getattr(cb, '__name__', rule.match)
            rules.append((rule.priority, appcallback_v1.TopicRule(match=rule.match, path=path)))
            rules.sort(key=lambda x: x[0])
            rs = [rule for id, rule in rules]
            del sub.routes.rules[:]
            sub.routes.rules.extend(rs)

    def register_binding(self, name: str, cb: BindingCallable) -> None:
        """Registers input bindings."""
        if name in self._binding_map:
            raise ValueError(f'{name} is already registered')
        self._binding_map[name] = cb
        self._registered_bindings.append(name)

    def register_job_event(self, name: str, cb: JobEventCallable) -> None:
        """Registers job event handler.

        Args:
            name (str): The name of the job to handle events for.
            cb (JobEventCallable): The callback function to handle job events.
        """
        if name in self._job_event_map:
            raise ValueError(f'Job event handler for {name} is already registered')
        self._job_event_map[name] = cb

    def _unimplemented(self, context: _ServicerContext, message: str) -> NotImplementedError:
        """Marks the RPC UNIMPLEMENTED and returns the error for the caller to raise."""
        context.set_code(grpc.StatusCode.UNIMPLEMENTED)  # type: ignore
        return NotImplementedError(message)

    def _build_invoke_request(
        self, request: InvokeRequest, context: _ServicerContext
    ) -> InvokeMethodRequest:
        """Translates an InvokeRequest into the request object handlers receive."""
        req = InvokeMethodRequest(request.data, request.content_type)
        req.metadata = context.invocation_metadata()
        return req

    def _to_invoke_response_data(
        self, resp: HandlerResponse, context: _ServicerContext, method: str
    ) -> InvokeMethodResponse:
        """Normalizes a method handler's return value into an InvokeMethodResponse."""
        if isinstance(resp, InvokeMethodResponse):
            return resp

        resp_data = InvokeMethodResponse()
        if isinstance(resp, (bytes, str)):
            resp_data.set_data(resp)
            resp_data.content_type = DEFAULT_JSON_CONTENT_TYPE
            return resp_data
        if isinstance(resp, GrpcMessage):
            resp_data.set_data(resp)
            return resp_data

        context.set_code(grpc.StatusCode.OUT_OF_RANGE)
        context.set_details(f'{type(resp)} is the invalid return type.')
        raise NotImplementedError(f'{method} method not implemented!')

    def _to_invoke_response(self, resp_data: InvokeMethodResponse) -> common_v1.InvokeResponse:
        """Packs a normalized handler response into the wire InvokeResponse."""
        content_type = ''
        if resp_data.content_type:
            content_type = resp_data.content_type
        return common_v1.InvokeResponse(data=resp_data.proto, content_type=content_type)

    def _build_topic_event(
        self,
        cb: TopicSubscribeCallable,
        request: TopicEventRequest,
        invocation_metadata: Dict[str, str],
    ) -> Union[v1.Event, SubscriptionMessage]:
        """Translates a topic event request into the event type the handler expects."""
        if not self._topic_legacy_event.get(cb, True):
            return SubscriptionMessage(request, invocation_metadata)

        customdata: Struct = request.extensions
        extensions = dict()
        for k, v in customdata.items():
            extensions[k] = v
        for k, v in invocation_metadata.items():
            extensions['_metadata_' + k] = v

        event = v1.Event()
        event.SetEventType(request.type)
        event.SetEventID(request.id)
        event.SetSource(request.source)
        event.SetData(request.data)
        event.SetContentType(request.data_content_type)
        event.SetSubject(request.topic)
        event.SetExtensions(extensions)
        return event

    def _to_topic_event_response(
        self, response: Optional[TopicEventResponse]
    ) -> Union[appcallback_v1.TopicEventResponse, empty_pb2.Empty]:
        """Maps a topic handler's return value to the single-event wire response."""
        if isinstance(response, TopicEventResponse):
            return appcallback_v1.TopicEventResponse(status=response.status.value)
        return empty_pb2.Empty()

    def _build_binding_request(
        self, request: BindingEventRequest, context: _ServicerContext
    ) -> BindingRequest:
        """Translates a binding event request into the request object handlers receive."""
        req = BindingRequest(request.data, dict(request.metadata))
        req.metadata = context.invocation_metadata()
        return req

    def _build_job_event(self, request: JobEventRequest, context: _ServicerContext) -> JobEvent:
        """Translates a job event request into the JobEvent handlers receive.

        Raises NotImplementedError (UNIMPLEMENTED) when no handler is registered for the job.
        """
        if request.name not in self._job_event_map:
            raise self._unimplemented(
                context, f'Job event handler for {request.name} not implemented!'
            )

        # Create a JobEvent object matching Go SDK's common.JobEvent
        # Extract raw data bytes from the Any proto (matching Go implementation)
        data_bytes = b''
        if request.HasField('data') and request.data.value:
            data_bytes = request.data.value

        return JobEvent(name=request.name, data=data_bytes)

    def _warn_bulk_alpha1_deprecated(self) -> None:
        """Emits the shared deprecation warning for the alpha bulk-topic entry point."""
        warnings.warn(
            'OnBulkTopicEventAlpha1 is deprecated. Use OnBulkTopicEvent instead.',
            DeprecationWarning,
            stacklevel=3,
        )

    def _bulk_entry_event(
        self,
        entry: TopicEventBulkRequestEntry,
        request: TopicEventBulkRequest,
        use_legacy_event: bool,
        invocation_metadata: Dict[str, str],
    ) -> Union[v1.Event, SubscriptionMessage]:
        """Translates one bulk entry into the event type the handler expects."""
        if use_legacy_event:
            return self._bulk_entry_legacy_event(entry, request, invocation_metadata)
        return self._bulk_entry_subscription_message(entry, request, invocation_metadata)

    def _bulk_entry_status(
        self, response: Optional[TopicEventResponse]
    ) -> appcallback_v1.TopicEventResponse.TopicEventResponseStatus.ValueType:
        """Maps a topic handler's return value to a bulk-response entry status."""
        if isinstance(response, TopicEventResponse):
            return response.status.value
        return appcallback_v1.TopicEventResponse.TopicEventResponseStatus.SUCCESS

    def _bulk_entry_legacy_event(
        self,
        entry: TopicEventBulkRequestEntry,
        request: TopicEventBulkRequest,
        invocation_metadata: Dict[str, str],
    ) -> v1.Event:
        """Builds the deprecated cloudevents v1.Event for a bulk entry."""
        event = v1.Event()
        extensions = dict()
        if entry.HasField('cloud_event') and entry.cloud_event:
            ce = entry.cloud_event
            event.SetEventType(ce.type)
            event.SetEventID(ce.id)
            event.SetSource(ce.source)
            event.SetData(ce.data)
            event.SetContentType(ce.data_content_type)
            if ce.extensions:
                for k, v in ce.extensions.items():
                    extensions[k] = v
        else:
            event.SetEventID(entry.entry_id)
            event.SetData(entry.bytes if entry.HasField('bytes') else b'')
            event.SetContentType(entry.content_type or '')
        event.SetSubject(request.topic)
        if entry.metadata:
            for k, v in entry.metadata.items():
                extensions[k] = v
        for k, v in invocation_metadata.items():
            extensions['_metadata_' + k] = v
        if extensions:
            event.SetExtensions(extensions)
        return event

    def _bulk_entry_subscription_message(
        self,
        entry: TopicEventBulkRequestEntry,
        request: TopicEventBulkRequest,
        invocation_metadata: Dict[str, str],
    ) -> SubscriptionMessage:
        """Builds a SubscriptionMessage for a bulk entry via a synthesized TopicEventRequest."""
        if entry.HasField('cloud_event') and entry.cloud_event:
            ce = entry.cloud_event
            entry_request = TopicEventRequest(
                id=ce.id,
                source=ce.source,
                type=ce.type,
                spec_version=ce.spec_version,
                data_content_type=ce.data_content_type,
                data=ce.data,
                topic=request.topic,
                pubsub_name=request.pubsub_name,
                extensions=ce.extensions,
            )
        else:
            entry_request = TopicEventRequest(
                id=entry.entry_id,
                data=entry.bytes if entry.HasField('bytes') else b'',
                data_content_type=entry.content_type or '',
                topic=request.topic,
                pubsub_name=request.pubsub_name,
            )
        metadata = {**invocation_metadata, **dict(entry.metadata)}
        return SubscriptionMessage(entry_request, metadata)


class _CallbackServicer(_CallbackServicerBase):
    """The implementation of AppCallback Server.

    This internal class implements application server and provides helpers to register
    method, topic, and input bindings. It implements the routing handling logic to route
    mulitple methods, topics, and bindings.

    :class:`App` provides useful decorators to register method, topic, input bindings.
    """

    def OnInvoke(self, request: InvokeRequest, context):
        """Invokes service method with InvokeRequest."""
        if request.method not in self._invoke_method_map:
            raise self._unimplemented(context, f'{request.method} method not implemented!')

        req = self._build_invoke_request(request, context)
        resp = self._invoke_method_map[request.method](req)

        if not resp:
            return common_v1.InvokeResponse()

        resp_data = self._to_invoke_response_data(resp, context, request.method)

        headers = resp_data.get_headers()
        if len(headers) > 0:
            context.send_initial_metadata(headers)

        return self._to_invoke_response(resp_data)

    def ListTopicSubscriptions(self, request, context):
        """Lists all topics subscribed by this app."""
        return appcallback_v1.ListTopicSubscriptionsResponse(subscriptions=self._registered_topics)

    def OnTopicEvent(self, request: TopicEventRequest, context):
        """Subscribes events from Pubsub."""
        cb = self._get_topic_callback(request.pubsub_name, request.topic, request.path)
        if cb is None:
            raise self._unimplemented(context, f'topic {request.topic} is not implemented!')

        event = self._build_topic_event(cb, request, dict(context.invocation_metadata()))

        return self._to_topic_event_response(cb(event))

    def ListInputBindings(self, request, context):
        """Lists all input bindings subscribed by this app."""
        return appcallback_v1.ListInputBindingsResponse(bindings=self._registered_bindings)

    def OnBindingEvent(self, request: BindingEventRequest, context):
        """Listens events from the input bindings
        User application can save the states or send the events to the output
        bindings optionally by returning BindingEventResponse.
        """
        if request.name not in self._binding_map:
            raise self._unimplemented(context, f'{request.name} binding not implemented!')

        req = self._build_binding_request(request, context)
        self._binding_map[request.name](req)

        # TODO: support output bindings options
        return appcallback_v1.BindingEventResponse()

    def _handle_job_event(self, request: JobEventRequest, context):
        """Handles job events from Dapr runtime.

        This method is called by Dapr when a scheduled job is triggered.
        It routes the job event to the appropriate registered handler based on the job name.

        Args:
            request (JobEventRequest): The job event request from Dapr.
            context: The gRPC context.

        Returns:
            appcallback_v1.JobEventResponse: Empty response indicating successful handling.
        """
        job_event = self._build_job_event(request, context)
        self._job_event_map[request.name](job_event)
        return appcallback_v1.JobEventResponse()

    def OnJobEvent(self, request: JobEventRequest, context):
        """Handles job events on the stable AppCallback service."""
        return self._handle_job_event(request, context)

    def OnJobEventAlpha1(self, request: JobEventRequest, context):
        """Handles job events on the deprecated AppCallbackAlpha service."""
        return self._handle_job_event(request, context)

    def _handle_bulk_topic_event(
        self, request: TopicEventBulkRequest, context: _ServicerContext
    ) -> TopicEventBulkResponse:
        """Process bulk topic event request - routes each entry to the appropriate topic handler."""
        cb = self._get_topic_callback(request.pubsub_name, request.topic, request.path)
        if cb is None:
            raise self._unimplemented(context, f'bulk topic {request.topic} is not implemented!')

        use_legacy_event = self._topic_legacy_event.get(cb, True)
        invocation_metadata = dict(context.invocation_metadata())

        statuses = []
        for entry in request.entries:
            entry_id = entry.entry_id
            try:
                event = self._bulk_entry_event(
                    entry, request, use_legacy_event, invocation_metadata
                )
                status = self._bulk_entry_status(cb(event))
            except Exception:
                status = appcallback_v1.TopicEventResponse.TopicEventResponseStatus.RETRY
            statuses.append(
                appcallback_v1.TopicEventBulkResponseEntry(entry_id=entry_id, status=status)
            )
        return appcallback_v1.TopicEventBulkResponse(statuses=statuses)

    def OnBulkTopicEvent(self, request: TopicEventBulkRequest, context):
        """Subscribes bulk events from Pubsub"""
        return self._handle_bulk_topic_event(request, context)

    def OnBulkTopicEventAlpha1(self, request: TopicEventBulkRequest, context):
        """Subscribes bulk events from Pubsub.
        Deprecated: Use OnBulkTopicEvent instead.
        """
        self._warn_bulk_alpha1_deprecated()
        return self._handle_bulk_topic_event(request, context)
