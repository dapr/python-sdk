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

import asyncio
import contextlib
import logging
from typing import Any, Callable, Dict, List, Optional, Tuple

import grpc.aio

from dapr.conf import settings
from dapr.ext.grpc._health_servicer import AsyncHealthCheckCallable
from dapr.ext.grpc._servicer import Rule  # type: ignore
from dapr.ext.grpc.aio._health_servicer import _AioHealthCheckServicer  # type: ignore
from dapr.ext.grpc.aio._servicer import _AioCallbackServicer  # type: ignore
from dapr.ext.grpc.app import _resolve_topic_event_type
from dapr.proto import appcallback_service_v1

logger = logging.getLogger(__name__)

ExternalServiceRegistration = Tuple[Callable[[Any, grpc.aio.Server], None], Any]


class App:
    """App object implements a Dapr application callback which can interact with Dapr runtime.

    This is the asyncio-native counterpart of :class:`dapr.ext.grpc.App`: it is backed by a
    ``grpc.aio`` server, so handlers may be ``async def`` and are awaited. The decorators take
    the same arguments as the synchronous app's, but return the handler so the decorated name
    stays bound (the synchronous decorators return ``None``).

    Differences from the synchronous app, all forced by the async runtime:

    * :meth:`run` and :meth:`stop` are coroutines, and :meth:`stop` takes a grace period.
    * :meth:`start` is a non-blocking alternative to :meth:`run`, for serving alongside other
      work on the same loop.
    * The gRPC server is built on the first :meth:`run`/:meth:`start` rather than in
      ``__init__``, because ``grpc.aio.server()`` binds to the loop current at creation.
      :meth:`add_external_service` must therefore be called **before** the app is started; it
      raises afterwards, where the synchronous app accepts it at any time.

    You can create a :class:`App` instance in your main module:

        import asyncio
        from dapr.ext.grpc.aio import App

        app = App()
        asyncio.run(app.run(50051))
    """

    def __init__(self, max_grpc_message_length: Optional[int] = None, **kwargs):
        """Inits App object. The gRPC server itself is created when the app is started.

        Args:
            max_grpc_message_length (int, optional): The maximum grpc send and receive
                message length in bytes. Only used when kwargs are not set. When this
                argument is omitted, the env var
                ``DAPR_GRPC_MAX_INBOUND_MESSAGE_SIZE_BYTES`` is consulted to set the
                receive limit (matches the Java SDK property of the same name).
            kwargs: arguments to grpc.aio.server()
        """
        self._servicer = _AioCallbackServicer()
        self._health_check_servicer = _AioHealthCheckServicer()
        self._server: Optional[grpc.aio.Server] = None
        self._listen_port: Optional[int] = None
        self._abandoned_servers: List[grpc.aio.Server] = []
        self._abandoned_ports: set[int] = set()
        self._lifecycle_lock: Optional[asyncio.Lock] = None
        self._lifecycle_loop: Optional[asyncio.AbstractEventLoop] = None
        self._external_services: List[ExternalServiceRegistration] = []

        if kwargs:
            self._server_kwargs: Dict[str, Any] = kwargs
            return

        options = []
        if max_grpc_message_length is not None:
            options = [
                ('grpc.max_send_message_length', max_grpc_message_length),
                ('grpc.max_receive_message_length', max_grpc_message_length),
            ]
        elif settings.DAPR_GRPC_MAX_INBOUND_MESSAGE_SIZE_BYTES:
            options = [
                (
                    'grpc.max_receive_message_length',
                    settings.DAPR_GRPC_MAX_INBOUND_MESSAGE_SIZE_BYTES,
                ),
            ]
        self._server_kwargs = {'options': options}

    def _lock_for_running_loop(self) -> asyncio.Lock:
        """Returns the start/stop lock, rebuilding it if the running loop has changed.

        Serialises start and stop, which grpc.aio cannot have in flight at the same time.
        An App is meant to be driven from one event loop; this guard catches the common
        mistake, but it is best effort — two loops racing their very first ``start()`` from
        different threads can each build a lock before either publishes one.
        The lock cannot be built in ``__init__``: an :class:`asyncio.Lock` binds to the loop
        of its first *contended* acquire, so one built there would raise "bound to a different
        event loop" on a second ``asyncio.run()`` — and, because the uncontended path returns
        before that check, would silently stop excluding anything in between.
        """
        loop = asyncio.get_running_loop()
        lock = self._lifecycle_lock
        owning_loop = self._lifecycle_loop
        if lock is not None and owning_loop is loop:
            return lock

        # Handing out a fresh lock for a foreign loop would destroy the exclusion entirely,
        # so a live server may only be driven from the loop that started it.
        if self._server is not None:
            raise RuntimeError(
                'app gRPC server was started on a different event loop. Stop it from that '
                'loop, or — if that loop is already closed — call stop() from this one to '
                'release it.'
            )

        lock = asyncio.Lock()
        self._lifecycle_lock = lock
        self._lifecycle_loop = loop
        return lock

    def _abandon_if_owning_loop_is_closed(self) -> bool:
        """Releases a server whose event loop is gone, warning that its port stays bound.

        Such a server cannot be shut down from here — grpc.aio needs its own loop to drain —
        but refusing would trap the App, since stop() is the documented remedy. The handle is
        dropped so the App becomes usable again, loudly, because the listener survives for
        the life of the process and grpc enables SO_REUSEPORT: restarting on the same port
        would bind a *second* server and the kernel would split callbacks between them.

        Returns:
            bool: True if a server was abandoned and the caller should stop.
        """
        owning_loop = self._lifecycle_loop
        if self._server is None or owning_loop is None or not owning_loop.is_closed():
            return False

        logger.warning(
            'Cannot stop the app gRPC server: the event loop it was started on is closed. '
            'Its listener stays bound until the process exits. Restarting on the same port '
            'would bind a second server alongside it, so choose a different port.'
        )
        # Parked rather than dropped: releasing the last reference fires grpc's
        # Server.__del__ against the closed loop, printing an "Event loop is closed"
        # traceback attributed to this file. Holding it defers that to interpreter exit.
        self._abandoned_servers.append(self._server)
        if self._listen_port is not None:
            self._abandoned_ports.add(self._listen_port)
        self._server = None
        self._lifecycle_lock = None
        self._lifecycle_loop = None
        return True

    def _create_server(self) -> grpc.aio.Server:
        """Builds the gRPC server and registers every servicer on it.

        ``grpc.aio.server()`` binds to whichever event loop is current when it is called, so
        the server cannot be built in ``__init__`` the way the synchronous App does — it has
        to be created inside the running loop that will serve requests.
        """
        server = grpc.aio.server(**self._server_kwargs)
        appcallback_service_v1.add_AppCallbackServicer_to_server(self._servicer, server)
        appcallback_service_v1.add_AppCallbackAlphaServicer_to_server(self._servicer, server)
        appcallback_service_v1.add_AppCallbackHealthCheckServicer_to_server(
            self._health_check_servicer, server
        )
        for servicer_callback, external_servicer in self._external_services:
            servicer_callback(external_servicer, server)
        return server

    async def _start(
        self, app_port: Optional[int] = None, listen_address: Optional[str] = None
    ) -> grpc.aio.Server:
        async with self._lock_for_running_loop():
            if self._server is not None:
                raise RuntimeError('app gRPC server is already running')

            if app_port is None:
                app_port = settings.GRPC_APP_PORT
            listen_addr = f'{listen_address if listen_address else "[::]"}:{app_port}'

            if app_port in self._abandoned_ports:
                logger.warning(
                    'Starting on port %s, which an abandoned server still holds. grpc enables '
                    'SO_REUSEPORT, so both will bind and callbacks will be split between them.',
                    app_port,
                )

            server = self._create_server()
            try:
                # add_insecure_port raises on grpc.aio when the port is taken, so it belongs
                # inside the guard: otherwise a bind failure strands a fully built server.
                server.add_insecure_port(listen_addr)
                # Published before the await so add_external_service(), which is sync and
                # takes no lock, rejects registrations for the whole of startup.
                self._server = server
                self._listen_port = app_port
                await server.start()
            except BaseException:
                self._server = None
                # start() has already unwound here, so this is sequential cleanup, not the
                # concurrent overlap the lock prevents. stop() is a no-op on a server that
                # never started, but raises InvalidStateError on one whose start() was
                # cancelled part-way. CancelledError is suppressed alongside normal errors
                # because the original failure is re-raised below; KeyboardInterrupt and
                # SystemExit deliberately are not.
                with contextlib.suppress(Exception, asyncio.CancelledError):
                    await server.stop(None)
                raise
            return server

    async def start(
        self, app_port: Optional[int] = None, listen_address: Optional[str] = None
    ) -> None:
        """Starts app gRPC server and returns once it is accepting requests.

        Use this instead of :meth:`run` to serve the app alongside other work on the same
        event loop, for example from an ASGI lifespan handler.

        Args:
            app_port (int, optional): The port on which to listen for incoming gRPC calls.
                Defaults to settings.GRPC_APP_PORT.
            listen_address (str, optional): The IP address on which to listen for incoming gRPC
                calls. Defaults to [::] (all IP addresses).
        """
        await self._start(app_port, listen_address)

    async def run(
        self, app_port: Optional[int] = None, listen_address: Optional[str] = None
    ) -> None:
        """Starts app gRPC server and waits until :class:`App`.stop() is called.

        Args:
            app_port (int, optional): The port on which to listen for incoming gRPC calls.
                Defaults to settings.GRPC_APP_PORT.
            listen_address (str, optional): The IP address on which to listen for incoming gRPC
                calls. Defaults to [::] (all IP addresses).
        """
        server = await self._start(app_port, listen_address)
        try:
            await server.wait_for_termination()
        finally:
            # Guarded on identity: if the app was stopped and restarted while this was
            # unwinding, self._server is a different server and is not ours to tear down.
            # The synchronous App relies on __del__ to stop its server; a coroutine cannot be
            # awaited from one, so cancellation (Ctrl-C, a wait_for timeout, a TaskGroup
            # teardown) would otherwise leave the listener bound and the App unrestartable.
            if self._server is server:
                await self.stop()

    async def stop(self, grace: Optional[float] = None) -> None:
        """Stops app server, letting in-flight requests finish within the grace period.

        Args:
            grace (float, optional): Seconds to wait for in-flight requests before cancelling
                them. Defaults to None, which cancels them immediately.
        """
        if self._abandon_if_owning_loop_is_closed():
            return

        # Waits for an in-flight start() rather than racing it, and holds the lock for the
        # whole drain so a restart cannot bind a second server to the same port.
        async with self._lock_for_running_loop():
            server = self._server
            if server is None:
                return
            try:
                await server.stop(grace)
            except asyncio.CancelledError:
                # A graceful drain that is cut short still has to release the socket, or the
                # next start() fails on bind. Force an immediate stop, then report it gone.
                with contextlib.suppress(Exception, asyncio.CancelledError):
                    await server.stop(None)
                self._server = None
                raise
            # Only cleared once the server is actually down. If stop() failed for any other
            # reason the server's state is unknown, and claiming it stopped would make the
            # next start() fail on bind rather than with an accurate "already running".
            self._server = None

    def add_external_service(
        self,
        servicer_callback: Callable[[Any, grpc.aio.Server], None],
        external_servicer: Any,
    ) -> None:
        """Adds an external gRPC service to the same server.

        The registration is replayed when the server is built by :meth:`run` or :meth:`start`,
        so it must be called before the app is started. A ``grpc.aio`` server does not accept
        new services once it is serving, so registering late raises rather than being dropped.

        Raises:
            RuntimeError: if the app has already been started.
        """
        if self._server is not None:
            raise RuntimeError(
                'add_external_service must be called before the app is started; '
                'a running gRPC server cannot accept new services'
            )
        self._external_services.append((servicer_callback, external_servicer))

    def register_health_check(self, health_check_callback: AsyncHealthCheckCallable) -> None:
        """Adds a health check callback

        The below example adds a basic health check to check Dapr gRPC is running

            app.register_health_check(lambda: None)
        """
        self._health_check_servicer.register_health_check(health_check_callback)

    def method(self, name: str) -> Callable:
        """A decorator that is used to register the method for the service invocation.

        Return JSON formatted data response::

            @app.method('start')
            async def start(request: InvokeMethodRequest):

                ...

                return json.dumps()

        Return Protocol buffer response::

            @app.method('start')
            async def start(request: InvokeMethodRequest):

                ...

                return CustomProtoResponse(data='hello world')


        Specify Response header::

            @app.method('start')
            async def start(request: InvokeMethodRequest):

                ...

                resp = InvokeMethodResponse('hello world', 'text/plain')
                resp.headers = ('key', 'value')

                return resp

        Args:
            name (str): name of invoked method
        """

        def decorator(func: Callable) -> Callable:
            self._servicer.register_method(name, func)
            return func

        return decorator

    def subscribe(
        self,
        pubsub_name: str,
        topic: str,
        metadata: Optional[Dict[str, str]] = None,
        dead_letter_topic: Optional[str] = None,
        rule: Optional[Rule] = None,
        disable_topic_validation: Optional[bool] = False,
    ) -> Callable:
        """A decorator that is used to register the subscribing topic method.

        The event type the handler receives is inferred from its annotation: annotate the
        event parameter with :class:`dapr.ext.grpc.SubscriptionMessage` to receive that type.
        Unannotated (or otherwise-annotated) handlers receive the deprecated
        ``cloudevents.sdk.event.v1.Event`` and trigger a :class:`DeprecationWarning`.

        The below example registers 'topic' subscription topic and pass custom
        metadata to pubsub component::

            from dapr.ext.grpc.aio import SubscriptionMessage

            @app.subscribe('pubsub_name', 'topic', metadata={'session-id': 'session-id-value'})
            async def topic(event: SubscriptionMessage) -> None:
                ...

        Args:
            pubsub_name (str): the name of the pubsub component
            topic (str): the topic name which is subscribed
            metadata (dict, optional): metadata which will be passed to pubsub component
                during initialization
            dead_letter_topic (str, optional): the dead letter topic name for the subscription
        """

        def decorator(func: Callable) -> Callable:
            handler_wants_subscription_message = _resolve_topic_event_type(func)
            self._servicer.register_topic(
                pubsub_name,
                topic,
                func,
                metadata,
                dead_letter_topic,
                rule,
                disable_topic_validation,
                legacy_cloudevent=not handler_wants_subscription_message,
            )
            return func

        return decorator

    def binding(self, name: str) -> Callable:
        """A decorator that is used to register input binding.

        The below registers input binding which this application subscribes:

            @app.binding('input')
            async def input(request: BindingRequest) -> None:
                ...

        Args:
            name (str): the name of invoked method
        """

        def decorator(func: Callable) -> Callable:
            self._servicer.register_binding(name, func)
            return func

        return decorator

    def job_event(self, name: str) -> Callable:
        """A decorator that is used to register job event handler.

        This decorator registers a handler for job events triggered by the Dapr scheduler.
        The handler will be called when a job with the specified name is triggered.

        The below registers a job event handler for jobs named 'my-job':

            from dapr.ext.grpc.aio import JobEvent

            @app.job_event('my-job')
            async def handle_my_job(job_event: JobEvent) -> None:
                print(f"Job {job_event.name} triggered")
                data_str = job_event.get_data_as_string()
                print(f"Job data: {data_str}")
                # Process the job...

        Args:
            name (str): the name of the job to handle events for
        """

        def decorator(func: Callable) -> Callable:
            self._servicer.register_job_event(name, func)
            return func

        return decorator
