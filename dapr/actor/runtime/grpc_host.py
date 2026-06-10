# -*- coding: utf-8 -*-

"""
Copyright 2026 The Dapr Authors
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

import asyncio
import logging
from typing import Awaitable, Callable, Optional, Protocol, Set, Type, TypeVar

import grpc.aio  # type: ignore
from grpc import StatusCode  # type: ignore[attr-defined]
from grpc.aio import AioRpcError

from dapr.actor.id import ActorId
from dapr.actor.runtime._grpc_callbacks import (
    CONTENT_TYPE_HEADER,
    JSON_CONTENT_TYPE,
    ActorCallbackNotFoundError,
    build_initial_request,
    build_invoke_error_payload,
    build_reminder_fire_body,
    build_timer_fire_body,
    extract_reentrancy_id,
    status_code_for_exception,
)
from dapr.actor.runtime.actor import Actor
from dapr.actor.runtime.context import ActorRuntimeContext
from dapr.actor.runtime.method_dispatcher import ActorMethodNotFoundError
from dapr.actor.runtime.runtime import ActorRuntime
from dapr.clients.grpc._channel import create_aio_channel
from dapr.clients.grpc.dapr_actor_grpc_client import DaprActorGrpcClient
from dapr.conf import settings
from dapr.proto import api_service_v1, api_v1
from dapr.serializers import DefaultJSONSerializer, Serializer

logger = logging.getLogger(__name__)

_TRANSIENT_STATUS_CODES = frozenset(
    {
        StatusCode.UNAVAILABLE,
        StatusCode.UNKNOWN,
        # Cloud proxies may terminate idle streams with RST_STREAM (INTERNAL).
        StatusCode.INTERNAL,
    }
)
_RECONNECT_DELAY_SECONDS = 1.0
_DRAIN_TIMEOUT_SECONDS = 5.0
_HANDSHAKE_TIMEOUT_SECONDS = 60.0
_GRPC_AIO_EOF = grpc.aio.EOF  # type: ignore[attr-defined]


def _log_dispatch_task_exception(task: 'asyncio.Task[None]') -> None:
    if task.cancelled():
        return
    exception = task.exception()
    if exception is not None:
        logger.error('Unhandled exception in actor dispatch task', exc_info=exception)


class _ActorCallbackRequest(Protocol):
    """The fields shared by every callback daprd pushes on the stream."""

    @property
    def id(self) -> str: ...

    @property
    def actor_type(self) -> str: ...


_CallbackRequestT = TypeVar('_CallbackRequestT', bound=_ActorCallbackRequest)


class _StreamSession:
    """One live SubscribeActorEventsAlpha1 connection.

    Serializes writes (gRPC forbids concurrent sends on a stream) and drops
    responses produced by handlers that outlive the connection, so a reply
    correlated to a dead stream is never sent on its successor.
    """

    def __init__(self, stream: grpc.aio.StreamStreamCall):
        self._stream = stream
        self._write_lock = asyncio.Lock()
        self._closed = False

    def close(self) -> None:
        self._closed = True

    async def send(self, message: api_v1.SubscribeActorEventsRequestAlpha1) -> None:
        async with self._write_lock:
            if self._closed:
                logger.debug('Dropping actor callback response for a closed stream')
                return
            try:
                await self._stream.write(message)
            except AioRpcError as error:
                self._closed = True
                logger.debug('Failed to write actor callback response: %s', error)


class ActorGrpcHost:
    """Hosts Dapr actors over an app-initiated gRPC stream. Alpha feature.

    Instead of exposing HTTP callback endpoints, the host dials daprd's gRPC
    port, opens the ``SubscribeActorEventsAlpha1`` stream, registers the actor
    types of :class:`ActorRuntime` and serves invocation, reminder, timer, and
    deactivation callbacks pushed over the stream. The app does not need an
    inbound port for actor callbacks; the open stream is the liveness signal.

    daprd must be configured with a gRPC app channel (``--app-protocol grpc``)
    and a daprd version that supports the ``SubscribeActorEventsAlpha1`` RPC.
    Hosting actors over HTTP extensions and this host in the same process is
    not supported: both share the process-global :class:`ActorRuntime`.

    Example:

        >>> from dapr.actor.runtime.grpc_host import ActorGrpcHost
        >>> host = ActorGrpcHost()
        >>> await host.register_actor(DemoActor)
        >>> await host.start()
        ... # actors now served over the stream
        >>> await host.stop()
    """

    def __init__(
        self,
        address: Optional[str] = None,
        timeout_seconds: int = settings.DAPR_HTTP_TIMEOUT_SECONDS,
    ):
        """Creates the host.

        Args:
            address (str, optional): daprd gRPC address. Defaults to the same
                resolution as the Dapr clients (``DAPR_GRPC_ENDPOINT``,
                ``DAPR_RUNTIME_HOST``/``DAPR_GRPC_PORT``).
            timeout_seconds (int): per-call timeout for the actors' outbound
                operations (state, reminders, timers, invocations).
        """
        self._address = address
        self._timeout_seconds = timeout_seconds
        self._channel: Optional[grpc.aio.Channel] = None
        self._actor_client: Optional[DaprActorGrpcClient] = None
        self._run_task: Optional[asyncio.Task] = None
        self._registered = asyncio.Event()
        self._stopping = False
        self._session: Optional[_StreamSession] = None
        self._dispatch_tasks: Set[asyncio.Task] = set()

    async def register_actor(
        self,
        actor: Type[Actor],
        message_serializer: Serializer = DefaultJSONSerializer(),
        state_serializer: Serializer = DefaultJSONSerializer(),
        actor_factory: Optional[Callable[[ActorRuntimeContext, ActorId], Actor]] = None,
    ) -> None:
        """Registers an :class:`Actor` to be hosted over the gRPC stream.

        Mirrors :meth:`ActorRuntime.register_actor` but wires the actor's
        outbound operations (state, reminders, timers, invocations) to daprd's
        gRPC API so the app is fully gRPC-native.

        Register every actor type before calling :meth:`start`: daprd learns
        the hosted types from the stream's registration message, so types
        registered later are only advertised after a reconnect.

        Args:
            actor (:class:`Actor`): Actor implementation.
            message_serializer (:class:`Serializer`): serializer for actor
                invocation request and response bodies.
            state_serializer (:class:`Serializer`): serializer for state values.
            actor_factory (Callable, optional): factory to create Actor objects.
        """
        await ActorRuntime.register_actor(
            actor,
            message_serializer,
            state_serializer,
            actor_factory=actor_factory,
            actor_client=self._get_actor_client(message_serializer),
        )

    async def start(self) -> None:
        """Connects to daprd and registers the hosted actor types.

        Returns once daprd has acknowledged the registration. A background
        task keeps serving callbacks and transparently reconnects (and
        re-registers) after transient stream drops until :meth:`stop` is
        called. Non-transient errors (e.g. a daprd without a gRPC app
        channel) are raised here, after the host is cleaned up.

        Raises:
            RuntimeError: when no actor type has been registered yet.
        """
        if self._run_task is not None:
            raise RuntimeError('ActorGrpcHost is already started')
        if not ActorRuntime.get_registered_actor_types():
            raise RuntimeError('Register at least one actor type before calling start()')

        self._stopping = False
        self._registered.clear()
        run_task = asyncio.create_task(self._run_loop())
        self._run_task = run_task

        try:
            registered_task = asyncio.create_task(self._registered.wait())
            done, _ = await asyncio.wait(
                {registered_task, run_task}, return_when=asyncio.FIRST_COMPLETED
            )
            if run_task in done:
                registered_task.cancel()
                # Surfaces the connection error; a clean exit without
                # registration can only mean stop() raced start().
                run_task.result()
        except BaseException:
            await self.close()
            raise
        # Failures past this point no longer have a start() call to land in;
        # the callback logs them and resets state so the host is restartable.
        run_task.add_done_callback(self._on_run_task_done)

    def _on_run_task_done(self, task: 'asyncio.Task[None]') -> None:
        """Handles the serving task ending after a successful registration."""
        if task.cancelled() or self._stopping:
            return
        exception = task.exception()
        if exception is None:
            return
        logger.error(
            'Actor event stream task failed; the host is no longer serving callbacks',
            exc_info=exception,
        )
        self._run_task = None
        self._registered.clear()

    async def stop(self) -> None:
        """Stops serving callbacks, leaving the host restartable.

        Cancels the stream and drains in-flight callbacks but keeps the gRPC
        channel and outbound actor client open. Those objects are wired into
        the already-registered :class:`ActorRuntime` managers, so closing them
        here would break a later :meth:`start` and any outbound actor op; use
        :meth:`close` for terminal teardown.
        """
        self._stopping = True
        if self._session is not None:
            self._session.close()
        if self._run_task is not None:
            self._run_task.cancel()
            try:
                await self._run_task
            except asyncio.CancelledError:
                pass
            except Exception as exception:  # noqa: BLE001
                logger.warning('Actor event stream task raised during stop: %r', exception)
            self._run_task = None
        await self._drain_dispatch_tasks()
        self._registered.clear()

    async def close(self) -> None:
        """Stops serving and releases the gRPC channel. Terminal.

        After ``close`` the host cannot be restarted, because the registered
        actor managers still reference the now-closed outbound client. Create
        a new host (and re-register actors) to host again.
        """
        await self.stop()
        if self._actor_client is not None:
            await self._actor_client.close()
            self._actor_client = None
        if self._channel is not None:
            await self._channel.close()
            self._channel = None

    async def run_forever(self) -> None:
        """Starts the host and serves callbacks until cancelled.

        Convenience entrypoint for apps whose sole purpose is hosting actors:

            >>> asyncio.run(host.run_forever())
        """
        await self.start()
        run_task = self._run_task
        if run_task is None:
            # The serving task already died between start() returning and
            # here; _on_run_task_done logged the failure.
            await self.close()
            raise RuntimeError('Actor event stream task failed during startup, see logs')
        try:
            await asyncio.shield(run_task)
        finally:
            await self.close()

    async def __aenter__(self) -> 'ActorGrpcHost':
        await self.start()
        return self

    async def __aexit__(self, exc_type, exc_value, traceback) -> None:
        await self.close()

    def _get_actor_client(self, serializer: Serializer) -> DaprActorGrpcClient:
        if self._channel is None:
            self._channel = create_aio_channel(self._address)
        if self._actor_client is None:
            self._actor_client = DaprActorGrpcClient(
                timeout=self._timeout_seconds, channel=self._channel, serializer=serializer
            )
        return self._actor_client

    async def _run_loop(self) -> None:
        while not self._stopping:
            try:
                await self._run_session()
                if self._stopping:
                    return
                logger.warning('Actor event stream closed by daprd, reconnecting...')
            except asyncio.TimeoutError:
                if self._stopping:
                    return
                logger.warning('Actor event stream registration timed out, reconnecting...')
            except AioRpcError as error:
                if self._stopping or error.code() == StatusCode.CANCELLED:
                    return
                if error.code() not in _TRANSIENT_STATUS_CODES:
                    logger.error(
                        'Actor event stream failed with non-transient error: %s (%s)',
                        error.details(),
                        error.code(),
                    )
                    raise
                logger.warning(
                    'Actor event stream disconnected: %s (%s), reconnecting...',
                    error.details(),
                    error.code(),
                )
            await self._wait_for_channel_ready()
            await asyncio.sleep(_RECONNECT_DELAY_SECONDS)

    async def _wait_for_channel_ready(self) -> None:
        """Waits for the gRPC channel to reconnect to daprd.

        gRPC-native equivalent of the sidecar health wait used by the
        streaming PubSub clients; bounded by ``DAPR_HEALTH_TIMEOUT`` so a
        permanently gone sidecar surfaces as an error instead of a silent
        hang.
        """
        if self._channel is None:
            return
        timeout = float(settings.DAPR_HEALTH_TIMEOUT)
        await asyncio.wait_for(self._channel.channel_ready(), timeout)

    async def _run_session(self) -> None:
        """Runs one stream connection: register, ack, then dispatch until it ends."""
        if self._channel is None:
            self._channel = create_aio_channel(self._address)
        stub = api_service_v1.DaprStub(self._channel)
        stream = stub.SubscribeActorEventsAlpha1()
        session = _StreamSession(stream)
        self._session = session

        try:
            initial_request = build_initial_request(ActorRuntime.get_actor_config())
            registration = api_v1.SubscribeActorEventsRequestAlpha1(initial_request=initial_request)
            await asyncio.wait_for(stream.write(registration), _HANDSHAKE_TIMEOUT_SECONDS)

            first_message = await asyncio.wait_for(stream.read(), _HANDSHAKE_TIMEOUT_SECONDS)
            is_ack = first_message not in (None, _GRPC_AIO_EOF) and first_message.HasField(
                'initial_response'
            )
            if not is_ack:
                raise RuntimeError(
                    f'Expected initial_response from daprd, received: {first_message}'
                )
            self._registered.set()
            logger.info(
                'Actor host registered over gRPC for types: %s',
                list(initial_request.entities),
            )

            while True:
                message = await stream.read()
                if message in (None, _GRPC_AIO_EOF):
                    return
                dispatch_task = asyncio.create_task(self._dispatch(session, message))
                self._dispatch_tasks.add(dispatch_task)
                dispatch_task.add_done_callback(self._dispatch_tasks.discard)
                dispatch_task.add_done_callback(_log_dispatch_task_exception)
        finally:
            session.close()
            self._session = None
            stream.cancel()

    async def _dispatch(
        self, session: _StreamSession, message: api_v1.SubscribeActorEventsResponseAlpha1
    ) -> None:
        """Routes one callback to the actor runtime and replies on the stream."""
        callback_type = message.WhichOneof('response_type')
        if callback_type == 'invoke_request':
            await self._guard_and_handle(session, message.invoke_request, self._on_invoke)
        elif callback_type == 'reminder_request':
            await self._guard_and_handle(session, message.reminder_request, self._on_reminder)
        elif callback_type == 'timer_request':
            await self._guard_and_handle(session, message.timer_request, self._on_timer)
        elif callback_type == 'deactivate_request':
            await self._guard_and_handle(session, message.deactivate_request, self._on_deactivate)
        else:
            logger.warning('Ignoring unexpected actor stream message: %s', callback_type)

    async def _guard_and_handle(
        self,
        session: _StreamSession,
        request: _CallbackRequestT,
        handler: Callable[[_StreamSession, _CallbackRequestT], Awaitable[None]],
    ) -> None:
        """Rejects callbacks for unhosted actor types, then runs the handler.

        Checking registration here means an unknown actor type maps to
        NOT_FOUND consistently across every callback kind (daprd treats it as
        a permanent failure).
        """
        if request.actor_type not in ActorRuntime.get_registered_actor_types():
            not_found = ActorCallbackNotFoundError(f'{request.actor_type} is not registered.')
            await self._send_request_failed(session, request.id, not_found)
            return
        await handler(session, request)

    async def _on_invoke(
        self,
        session: _StreamSession,
        request: api_v1.SubscribeActorEventsResponseInvokeRequestAlpha1,
    ) -> None:
        try:
            reentrancy_id = extract_reentrancy_id(request.metadata)
            result = await ActorRuntime.dispatch(
                request.actor_type, request.actor_id, request.method, request.data, reentrancy_id
            )
            response = api_v1.SubscribeActorEventsRequestInvokeResponseAlpha1(
                id=request.id,
                data=result,
                metadata={CONTENT_TYPE_HEADER: JSON_CONTENT_TYPE},
            )
        except ActorMethodNotFoundError as exception:
            # Raised by the method dispatcher for unknown actor methods; daprd
            # maps NOT_FOUND to a permanent, non-retryable failure. A plain
            # AttributeError from inside the actor's code is an application
            # error and falls through to the error-payload branch below.
            await self._send_request_failed(session, request.id, exception)
            return
        except Exception as exception:  # noqa: BLE001
            # Application-level handler failures travel back to the original
            # caller verbatim, matching the HTTP extensions' 500-body behavior.
            response = api_v1.SubscribeActorEventsRequestInvokeResponseAlpha1(
                id=request.id,
                data=build_invoke_error_payload(exception),
                metadata={CONTENT_TYPE_HEADER: JSON_CONTENT_TYPE},
                error=True,
            )
        await session.send(api_v1.SubscribeActorEventsRequestAlpha1(invoke_response=response))

    async def _on_reminder(
        self,
        session: _StreamSession,
        request: api_v1.SubscribeActorEventsResponseReminderRequestAlpha1,
    ) -> None:
        try:
            body = build_reminder_fire_body(request)
            await ActorRuntime.fire_reminder(
                request.actor_type, request.actor_id, request.name, body
            )
        except Exception as exception:  # noqa: BLE001
            await self._send_request_failed(session, request.id, exception)
            return
        reminder_response = api_v1.SubscribeActorEventsRequestReminderResponseAlpha1(id=request.id)
        await session.send(
            api_v1.SubscribeActorEventsRequestAlpha1(reminder_response=reminder_response)
        )

    async def _on_timer(
        self,
        session: _StreamSession,
        request: api_v1.SubscribeActorEventsResponseTimerRequestAlpha1,
    ) -> None:
        try:
            body = build_timer_fire_body(request)
            await ActorRuntime.fire_timer(request.actor_type, request.actor_id, request.name, body)
        except Exception as exception:  # noqa: BLE001
            await self._send_request_failed(session, request.id, exception)
            return
        timer_response = api_v1.SubscribeActorEventsRequestReminderResponseAlpha1(id=request.id)
        await session.send(api_v1.SubscribeActorEventsRequestAlpha1(timer_response=timer_response))

    async def _on_deactivate(
        self,
        session: _StreamSession,
        request: api_v1.SubscribeActorEventsResponseDeactivateRequestAlpha1,
    ) -> None:
        try:
            await ActorRuntime.deactivate(request.actor_type, request.actor_id)
        except Exception as exception:  # noqa: BLE001
            await self._send_request_failed(session, request.id, exception)
            return
        deactivate_response = api_v1.SubscribeActorEventsRequestDeactivateResponseAlpha1(
            id=request.id
        )
        await session.send(
            api_v1.SubscribeActorEventsRequestAlpha1(deactivate_response=deactivate_response)
        )

    async def _send_request_failed(
        self, session: _StreamSession, request_id: str, exception: Exception
    ) -> None:
        logger.warning('Actor callback %s failed: %r', request_id, exception)
        request_failed = api_v1.SubscribeActorEventsRequestFailedAlpha1(
            id=request_id,
            code=status_code_for_exception(exception),
            message=str(exception),
        )
        await session.send(api_v1.SubscribeActorEventsRequestAlpha1(request_failed=request_failed))

    async def _drain_dispatch_tasks(self) -> None:
        if not self._dispatch_tasks:
            return
        pending_tasks = list(self._dispatch_tasks)
        _, still_pending = await asyncio.wait(pending_tasks, timeout=_DRAIN_TIMEOUT_SECONDS)
        for task in still_pending:
            task.cancel()
        if still_pending:
            await asyncio.gather(*still_pending, return_exceptions=True)
