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

import grpc.aio

from typing import Callable, Dict, Optional, cast

from dapr.conf import settings
from dapr.ext.grpc.aio._health_servicer import _AioHealthCheckServicer  # type: ignore
from dapr.ext.grpc.aio._servicer import Rule, _AioCallbackServicer  # type: ignore
from dapr.proto import appcallback_service_v1


class App:
    """Asyncio-native App object for Dapr gRPC callbacks."""

    def __init__(self, max_grpc_message_length: Optional[int] = None, **kwargs):
        """Inits App object. Server creation is deferred.

        Args:
            max_grpc_messsage_length (int, optional): The maximum grpc send and receive
                message length in bytes. Only used when kwargs are not set.
            kwargs: arguments to grpc.server()
        """
        self._servicer = _AioCallbackServicer()
        self._health_check_servicer = _AioHealthCheckServicer()
        self._server: grpc.aio.Server | None = None

        if kwargs:
            self._grpc_server_kwargs = kwargs
        else:
            options = []
            if max_grpc_message_length is not None:
                options = [
                    ('grpc.max_send_message_length', max_grpc_message_length),
                    ('grpc.max_receive_message_length', max_grpc_message_length),
                ]
            self._grpc_server_kwargs = {'options': options}

    def _create_server(self):
        """Creates the gRPC server instance."""
        self._server = grpc.aio.server(**self._grpc_server_kwargs)  # type: ignore
        # Add the async servicers to the newly created server
        appcallback_service_v1.add_AppCallbackServicer_to_server(self._servicer, self._server)
        appcallback_service_v1.add_AppCallbackHealthCheckServicer_to_server(
            self._health_check_servicer, self._server
        )

    async def run(
        self, app_port: Optional[int] = None, listen_address: Optional[str] = None
    ) -> None:
        """Creates, starts the async app gRPC server and waits for termination.

        Args:
            app_port (int, optional): The port on which to listen for incoming gRPC calls.
                Defaults to settings.GRPC_APP_PORT.
            listen_address (str, optional): The IP address on which to listen for incoming gRPC
                calls. Defaults to [::] (all IP addresses).
        """

        # Initialize the gRPC aio server here to receive the correct asyncio loop
        self._create_server()
        self._server = cast(grpc.aio.Server, self._server)

        if app_port is None:
            app_port = settings.GRPC_APP_PORT
        self._server.add_insecure_port(f"{listen_address if listen_address else '[::]'}:{app_port}")
        await self._server.start()
        await self._server.wait_for_termination()

    async def stop(self, grace: Optional[float] = None) -> None:
        """Stops the async app server gracefully."""
        if self._server is None:
            return
        await self._server.stop(grace)

    def add_external_service(self, servicer_callback, external_servicer):
        servicer_callback(external_servicer, self._server)

    def register_health_check(self, health_check_callback: Callable):
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
        metadata: Optional[Dict[str, str]] = {},
        dead_letter_topic: Optional[str] = None,
        rule: Optional[Rule] = None,
        disable_topic_validation: Optional[bool] = False,
    ) -> Callable:
        """A decorator that is used to register the subscribing topic method.

        The below example registers 'topic' subscription topic and pass custom
        metadata to pubsub component::

            from cloudevents.sdk.event import v1

            @app.subscribe('pubsub_name', 'topic', metadata=(('session-id', 'session-id-value'),))
            async def topic(event: v1.Event) -> None:
                ...

        Args:
            pubsub_name (str): the name of the pubsub component
            topic (str): the topic name which is subscribed
            metadata (dict, optional): metadata which will be passed to pubsub component
                during initialization
            dead_letter_topic (str, optional): the dead letter topic name for the subscription
        """

        def decorator(func: Callable) -> Callable:
            self._servicer.register_topic(
                pubsub_name,
                topic,
                func,
                metadata,
                dead_letter_topic,
                rule,
                disable_topic_validation,
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

    def job_event(self, name: str):
        """A decorator that is used to register job event handler.

        This decorator registers a handler for job events triggered by the Dapr scheduler.
        The handler will be called when a job with the specified name is triggered.

        The below registers a job event handler for jobs named 'my-job':

            from dapr.ext.grpc import JobEvent

            @app.job_event('my-job')
            def handle_my_job(job_event: JobEvent) -> None:
                print(f"Job {job_event.name} triggered")
                data_str = job_event.get_data_as_string()
                print(f"Job data: {data_str}")
                # Process the job...

        Args:
            name (str): the name of the job to handle events for
        """

        def decorator(func):
            self._servicer.register_job_event(name, func)

        return decorator
