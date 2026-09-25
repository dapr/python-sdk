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

import inspect
import warnings
from concurrent import futures
from typing import Callable, Dict, Optional, get_type_hints

import grpc

from dapr.common.pubsub.subscription import SubscriptionMessage
from dapr.conf import settings
from dapr.ext.grpc._health_servicer import _HealthCheckServicer  # type: ignore
from dapr.ext.grpc._servicer import Rule, _CallbackServicer  # type: ignore
from dapr.proto import appcallback_service_v1


def _wants_subscription_message(func: Callable) -> bool:
    """True if the handler's first parameter is annotated with SubscriptionMessage.

    Falls back to False (legacy cloudevents delivery) whenever the signature or the
    annotation cannot be resolved, so inference never breaks registration.
    """
    try:
        parameters = list(inspect.signature(func).parameters.values())
        resolved_hints = get_type_hints(func)
    except Exception:
        return False
    if not parameters:
        return False
    annotation = resolved_hints.get(parameters[0].name)
    return isinstance(annotation, type) and issubclass(annotation, SubscriptionMessage)


class App:
    """App object implements a Dapr application callback which can interact with Dapr runtime.
    Once its object is initiated, it will act as a central registry for service invocation,
    subscribing topic, and input bindings.

    You can create a :class:`App` instance in your main module:

        from dapr.ext.grpc import App
        app = App()
    """

    def __init__(self, max_grpc_message_length: Optional[int] = None, **kwargs):
        """Inits App object and creates gRPC server.

        Args:
            max_grpc_message_length (int, optional): The maximum grpc send and receive
                message length in bytes. Only used when kwargs are not set. When this
                argument is omitted, the env var
                ``DAPR_GRPC_MAX_INBOUND_MESSAGE_SIZE_BYTES`` is consulted to set the
                receive limit (matches the Java SDK property of the same name).
            kwargs: arguments to grpc.server()
        """
        self._servicer = _CallbackServicer()
        self._health_check_servicer = _HealthCheckServicer()
        if not kwargs:
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
            self._server = grpc.server(  # type: ignore
                futures.ThreadPoolExecutor(max_workers=10), options=options
            )
        else:
            self._server = grpc.server(**kwargs)  # type: ignore
        appcallback_service_v1.add_AppCallbackServicer_to_server(self._servicer, self._server)
        appcallback_service_v1.add_AppCallbackAlphaServicer_to_server(self._servicer, self._server)
        appcallback_service_v1.add_AppCallbackHealthCheckServicer_to_server(
            self._health_check_servicer, self._server
        )

    def __del__(self):
        self.stop()

    def add_external_service(self, servicer_callback, external_servicer):
        """Adds an external gRPC service to the same server"""
        servicer_callback(external_servicer, self._server)

    def register_health_check(self, health_check_callback):
        """Adds a health check callback

        The below example adds a basic health check to check Dapr gRPC is running

            @app.register_health_check(lambda: None)
        """
        self._health_check_servicer.register_health_check(health_check_callback)

    def run(self, app_port: Optional[int] = None, listen_address: Optional[str] = None) -> None:
        """Starts app gRPC server and waits until :class:`App`.stop() is called.

        Args:
            app_port (int, optional): The port on which to listen for incoming gRPC calls.
                Defaults to settings.GRPC_APP_PORT.
            listen_address (str, optional): The IP address on which to listen for incoming gRPC
                calls. Defaults to [::] (all IP addresses).
        """
        if app_port is None:
            app_port = settings.GRPC_APP_PORT
        self._server.add_insecure_port(f'{listen_address if listen_address else "[::]"}:{app_port}')
        self._server.start()
        self._server.wait_for_termination()

    def stop(self) -> None:
        """Stops app server."""
        self._server.stop(0)

    def method(self, name: str):
        """A decorator that is used to register the method for the service invocation.

        Return JSON formatted data response::

            @app.method('start')
            def start(request: InvokeMethodRequest):

                ...

                return json.dumps()

        Return Protocol buffer response::

            @app.method('start')
            def start(request: InvokeMethodRequest):

                ...

                return CustomProtoResponse(data='hello world')


        Specify Response header::

            @app.method('start')
            def start(request: InvokeMethodRequest):

                ...

                resp = InvokeMethodResponse('hello world', 'text/plain')
                resp.headers = ('key', 'value')

                return resp

        Args:
            name (str): name of invoked method
        """

        def decorator(func):
            self._servicer.register_method(name, func)

        return decorator

    def subscribe(
        self,
        pubsub_name: str,
        topic: str,
        metadata: Optional[Dict[str, str]] = {},
        dead_letter_topic: Optional[str] = None,
        rule: Optional[Rule] = None,
        disable_topic_validation: Optional[bool] = False,
    ):
        """A decorator that is used to register the subscribing topic method.

        The event type the handler receives is inferred from its annotation: annotate the
        event parameter with :class:`dapr.ext.grpc.SubscriptionMessage` to receive that type.
        Unannotated (or otherwise-annotated) handlers receive the deprecated
        ``cloudevents.sdk.event.v1.Event`` and trigger a :class:`DeprecationWarning`.

        The below example registers 'topic' subscription topic and pass custom
        metadata to pubsub component::

            from dapr.ext.grpc import SubscriptionMessage

            @app.subscribe('pubsub_name', 'topic', metadata={'session-id': 'session-id-value'})
            def topic(event: SubscriptionMessage) -> None:
                ...

        Args:
            pubsub_name (str): the name of the pubsub component
            topic (str): the topic name which is subscribed
            metadata (dict, optional): metadata which will be passed to pubsub component
                during initialization
            dead_letter_topic (str, optional): the dead letter topic name for the subscription
        """

        def decorator(func):
            handler_wants_subscription_message = _wants_subscription_message(func)
            if not handler_wants_subscription_message:
                warnings.warn(
                    'Topic handlers receive a deprecated cloudevents.sdk.event.v1.Event unless '
                    'their event parameter is annotated with dapr.ext.grpc.SubscriptionMessage. '
                    'Annotate the handler to adopt SubscriptionMessage and silence this warning; '
                    'a future release will deliver SubscriptionMessage to all handlers and drop '
                    'the cloudevents dependency.',
                    DeprecationWarning,
                    stacklevel=2,
                )
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

        return decorator

    def binding(self, name: str):
        """A decorator that is used to register input binding.

        The below registers input binding which this application subscribes:

            @app.binding('input')
            def input(request: BindingRequest) -> None:
                ...

        Args:
            name (str): the name of invoked method
        """

        def decorator(func):
            self._servicer.register_binding(name, func)

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
