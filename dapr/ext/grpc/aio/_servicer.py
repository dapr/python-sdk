# -*- coding: utf-8 -*-

"""
Copyright 2025 The Dapr Authors
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

import inspect
from typing import Any, Awaitable, Protocol, TypeGuard

from dapr.ext.grpc._servicer import _CallbackServicerBase, _ServicerContext
from dapr.proto import appcallback_v1, common_v1
from dapr.proto.common.v1.common_pb2 import InvokeRequest
from dapr.proto.runtime.v1.appcallback_pb2 import (
    BindingEventRequest,
    JobEventRequest,
    TopicEventBulkRequest,
    TopicEventBulkResponse,
    TopicEventRequest,
)


class _AioServicerContext(_ServicerContext, Protocol):
    """The ``grpc.aio`` servicer context surface this servicer relies on.

    Extends the shared protocol with ``send_initial_metadata``, which is a coroutine here but
    a plain method on the synchronous context — the difference that makes a single shared
    protocol impossible.
    """

    async def send_initial_metadata(self, initial_metadata: Any) -> None: ...


def _needs_await(result: Any) -> TypeGuard[Awaitable[Any]]:
    """True if a handler's return value still has to be awaited.

    The test is on the returned value, not on the handler: an ``async def`` handler yields a
    coroutine, while a plain function's value is already final. Plain handlers are accepted so
    trivial ones (and ``register_health_check(lambda: None)``) keep working, but they run
    inline on the event loop and must not block. Deliberately not a coroutine function - every
    RPC calls this, and wrapping a two-line test would allocate a coroutine per request.

    Returns:
        bool: True if ``result`` is awaitable, narrowed for the type checker.
    """
    return inspect.isawaitable(result)


class _AioCallbackServicer(_CallbackServicerBase):
    """The asyncio-native implementation of the AppCallback Server.

    Shares its handler registries, topic routing, and request translation with the
    synchronous :class:`dapr.ext.grpc._servicer._CallbackServicer` via their common base.
    Only the gRPC entry points are redefined here: they await the handler result and the
    ``grpc.aio`` context coroutines.
    """

    async def OnInvoke(self, request: InvokeRequest, context: _AioServicerContext):
        """Invokes service method with InvokeRequest."""
        if request.method not in self._invoke_method_map:
            raise self._unimplemented(context, f'{request.method} method not implemented!')

        req = self._build_invoke_request(request, context)
        resp = self._invoke_method_map[request.method](req)
        if _needs_await(resp):
            resp = await resp

        if not resp:
            return common_v1.InvokeResponse()

        resp_data = self._to_invoke_response_data(resp, context, request.method)

        headers = resp_data.get_headers()
        if len(headers) > 0:
            # grpc.aio's ServicerContext.send_initial_metadata is a coroutine, unlike the
            # synchronous context's method of the same name.
            await context.send_initial_metadata(headers)

        return self._to_invoke_response(resp_data)

    async def ListTopicSubscriptions(self, request, context: _AioServicerContext):
        """Lists all topics subscribed by this app."""
        return appcallback_v1.ListTopicSubscriptionsResponse(subscriptions=self._registered_topics)

    async def OnTopicEvent(self, request: TopicEventRequest, context: _AioServicerContext):
        """Subscribes events from Pubsub."""
        cb = self._get_topic_callback(request.pubsub_name, request.topic, request.path)
        if cb is None:
            raise self._unimplemented(context, f'topic {request.topic} is not implemented!')

        event = self._build_topic_event(cb, request, dict(context.invocation_metadata()))
        response = cb(event)
        if _needs_await(response):
            response = await response

        return self._to_topic_event_response(response)

    async def ListInputBindings(self, request, context: _AioServicerContext):
        """Lists all input bindings subscribed by this app."""
        return appcallback_v1.ListInputBindingsResponse(bindings=self._registered_bindings)

    async def OnBindingEvent(self, request: BindingEventRequest, context: _AioServicerContext):
        """Listens events from the input bindings
        User application can save the states or send the events to the output
        bindings optionally by returning BindingEventResponse.
        """
        if request.name not in self._binding_map:
            raise self._unimplemented(context, f'{request.name} binding not implemented!')

        req = self._build_binding_request(request, context)
        binding_result = self._binding_map[request.name](req)
        if _needs_await(binding_result):
            await binding_result

        # TODO: support output bindings options
        return appcallback_v1.BindingEventResponse()

    async def _handle_job_event(self, request: JobEventRequest, context: _AioServicerContext):
        """Routes a job event to the handler registered for its job name."""
        job_event = self._build_job_event(request, context)
        job_result = self._job_event_map[request.name](job_event)
        if _needs_await(job_result):
            await job_result
        return appcallback_v1.JobEventResponse()

    async def OnJobEvent(self, request: JobEventRequest, context: _AioServicerContext):
        """Handles job events on the stable AppCallback service."""
        return await self._handle_job_event(request, context)

    async def OnJobEventAlpha1(self, request: JobEventRequest, context: _AioServicerContext):
        """Handles job events on the deprecated AppCallbackAlpha service."""
        return await self._handle_job_event(request, context)

    async def _handle_bulk_topic_event(
        self, request: TopicEventBulkRequest, context: _AioServicerContext
    ) -> TopicEventBulkResponse:
        """Process bulk topic event request - routes each entry to the appropriate topic handler."""
        cb = self._get_topic_callback(request.pubsub_name, request.topic, request.path)
        if cb is None:
            raise self._unimplemented(context, f'bulk topic {request.topic} is not implemented!')

        use_legacy_event = self._topic_legacy_event.get(cb, True)
        invocation_metadata = dict(context.invocation_metadata())

        # Entries are handled one at a time, matching the synchronous servicer's delivery
        # order. Gathering them would let a batch overtake itself, so concurrency here is a
        # deliberate non-goal; the per-RPC path is where the event loop pays off.
        statuses = []
        for entry in request.entries:
            entry_id = entry.entry_id
            try:
                event = self._bulk_entry_event(
                    entry, request, use_legacy_event, invocation_metadata
                )
                entry_response = cb(event)
                if _needs_await(entry_response):
                    entry_response = await entry_response
                status = self._bulk_entry_status(entry_response)
            except Exception:
                status = appcallback_v1.TopicEventResponse.TopicEventResponseStatus.RETRY
            statuses.append(
                appcallback_v1.TopicEventBulkResponseEntry(entry_id=entry_id, status=status)
            )
        return appcallback_v1.TopicEventBulkResponse(statuses=statuses)

    async def OnBulkTopicEvent(self, request: TopicEventBulkRequest, context: _AioServicerContext):
        """Subscribes bulk events from Pubsub"""
        return await self._handle_bulk_topic_event(request, context)

    async def OnBulkTopicEventAlpha1(
        self, request: TopicEventBulkRequest, context: _AioServicerContext
    ):
        """Subscribes bulk events from Pubsub.
        Deprecated: Use OnBulkTopicEvent instead.
        """
        self._warn_bulk_alpha1_deprecated()
        return await self._handle_bulk_topic_event(request, context)
