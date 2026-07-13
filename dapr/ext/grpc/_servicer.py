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
from typing import Callable, Dict, List, Optional, Tuple, Union

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


class _CallbackServicer(
    appcallback_service_v1.AppCallbackServicer, appcallback_service_v1.AppCallbackAlphaServicer
):
    """The implementation of AppCallback Server.

    This internal class implements application server and provides helpers to register
    method, topic, and input bindings. It implements the routing handling logic to route
    mulitple methods, topics, and bindings.

    :class:`App` provides useful decorators to register method, topic, input bindings.
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

    def OnInvoke(self, request: InvokeRequest, context):
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

        content_type = ''
        if resp_data.content_type:
            content_type = resp_data.content_type

        return common_v1.InvokeResponse(data=resp_data.proto, content_type=content_type)

    def ListTopicSubscriptions(self, request, context):
        """Lists all topics subscribed by this app."""
        return appcallback_v1.ListTopicSubscriptionsResponse(subscriptions=self._registered_topics)

    def OnTopicEvent(self, request: TopicEventRequest, context):
        """Subscribes events from Pubsub."""
        cb = self._get_topic_callback(request.pubsub_name, request.topic, request.path)
        if cb is None:
            context.set_code(grpc.StatusCode.UNIMPLEMENTED)  # type: ignore
            raise NotImplementedError(f'topic {request.topic} is not implemented!')

        invocation_metadata = dict(context.invocation_metadata())

        event: Union[v1.Event, SubscriptionMessage]
        if self._topic_legacy_event.get(cb, True):
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
        else:
            event = SubscriptionMessage(request, invocation_metadata)

        response = cb(event)
        if isinstance(response, TopicEventResponse):
            return appcallback_v1.TopicEventResponse(status=response.status.value)
        return empty_pb2.Empty()

    def ListInputBindings(self, request, context):
        """Lists all input bindings subscribed by this app."""
        return appcallback_v1.ListInputBindingsResponse(bindings=self._registered_bindings)

    def OnBindingEvent(self, request: BindingEventRequest, context):
        """Listens events from the input bindings
        User application can save the states or send the events to the output
        bindings optionally by returning BindingEventResponse.
        """
        if request.name not in self._binding_map:
            context.set_code(grpc.StatusCode.UNIMPLEMENTED)  # type: ignore
            raise NotImplementedError(f'{request.name} binding not implemented!')

        req = BindingRequest(request.data, dict(request.metadata))
        req.metadata = context.invocation_metadata()
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
        job_name = request.name

        if job_name not in self._job_event_map:
            context.set_code(grpc.StatusCode.UNIMPLEMENTED)  # type: ignore
            raise NotImplementedError(f'Job event handler for {job_name} not implemented!')

        # Create a JobEvent object matching Go SDK's common.JobEvent
        # Extract raw data bytes from the Any proto (matching Go implementation)
        data_bytes = b''
        if request.HasField('data') and request.data.value:
            data_bytes = request.data.value

        job_event = JobEvent(name=request.name, data=data_bytes)

        # Call the registered handler with the JobEvent object
        self._job_event_map[job_name](job_event)

        # Return empty response
        return appcallback_v1.JobEventResponse()

    def OnJobEvent(self, request: JobEventRequest, context):
        """Handles job events on the stable AppCallback service."""
        return self._handle_job_event(request, context)

    def OnJobEventAlpha1(self, request: JobEventRequest, context):
        """Handles job events on the deprecated AppCallbackAlpha service."""
        return self._handle_job_event(request, context)

    def _handle_bulk_topic_event(
        self, request: TopicEventBulkRequest, context
    ) -> Optional[TopicEventBulkResponse]:
        """Process bulk topic event request - routes each entry to the appropriate topic handler."""
        cb = self._get_topic_callback(request.pubsub_name, request.topic, request.path)
        if cb is None:
            return None  # we don't have a handler

        use_legacy_event = self._topic_legacy_event.get(cb, True)
        invocation_metadata = dict(context.invocation_metadata())

        statuses = []
        for entry in request.entries:
            entry_id = entry.entry_id
            try:
                event: Union[v1.Event, SubscriptionMessage]
                if use_legacy_event:
                    event = self._bulk_entry_legacy_event(entry, request, invocation_metadata)
                else:
                    event = self._bulk_entry_subscription_message(
                        entry, request, invocation_metadata
                    )

                response = cb(event)  # invoke app registered handler and send event
                if isinstance(response, TopicEventResponse):
                    status = response.status.value
                else:
                    status = appcallback_v1.TopicEventResponse.TopicEventResponseStatus.SUCCESS
            except Exception:
                status = appcallback_v1.TopicEventResponse.TopicEventResponseStatus.RETRY
            statuses.append(
                appcallback_v1.TopicEventBulkResponseEntry(entry_id=entry_id, status=status)
            )
        return appcallback_v1.TopicEventBulkResponse(statuses=statuses)

    def _bulk_entry_legacy_event(
        self,
        entry,
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
        entry,
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

    def OnBulkTopicEvent(self, request: TopicEventBulkRequest, context):
        """Subscribes bulk events from Pubsub"""
        response = self._handle_bulk_topic_event(request, context)
        if response is None:
            context.set_code(grpc.StatusCode.UNIMPLEMENTED)  # type: ignore
            raise NotImplementedError(f'bulk topic {request.topic} is not implemented!')
        return response

    def OnBulkTopicEventAlpha1(self, request: TopicEventBulkRequest, context):
        """Subscribes bulk events from Pubsub.
        Deprecated: Use OnBulkTopicEvent instead.
        """
        warnings.warn(
            'OnBulkTopicEventAlpha1 is deprecated. Use OnBulkTopicEvent instead.',
            DeprecationWarning,
            stacklevel=2,
        )
        response = self._handle_bulk_topic_event(request, context)
        if response is None:
            context.set_code(grpc.StatusCode.UNIMPLEMENTED)  # type: ignore
            raise NotImplementedError(f'bulk topic {request.topic} is not implemented!')
        return response
