# -*- coding: utf-8 -*-

"""
Copyright (c) Microsoft Corporation.
Licensed under the MIT License.
"""

import grpc

from concurrent import futures
from typing import Dict, Optional

from dapr.conf import settings
from dapr.ext.grpc._servicier import _CallbackServicer   # type: ignore
from dapr.proto import appcallback_service_v1


class App:
    """App object implements a Dapr application callback which can interact with Dapr runtime.
    Once its object is initiated, it will act as a central registry for service invocation,
    subscribing topic, and input bindings.

    You can create a :class:`App` instance in your main module:

        from dapr.ext.grpc import App
        app = App()
    """

    def __init__(self, **kwargs):
        """Inits App object and creates gRPC server.

        Args:
            kwargs: arguments to grpc.server()
        """
        self._servicer = _CallbackServicer()
        if not kwargs:
            self._server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))   # type: ignore
        else:
            self._server = grpc.server(**kwargs)   # type: ignore
        appcallback_service_v1.add_AppCallbackServicer_to_server(self._servicer, self._server)

    def __del__(self):
        self.stop()

    def run(self, app_port: Optional[int]) -> None:
        """Starts app gRPC server and waits until :class:`App`.stop() is called."""
        if app_port is None:
            app_port = settings.GRPC_APP_PORT
        self._server.add_insecure_port(f'[::]:{app_port}')
        self._server.start()
        self._server.wait_for_termination()

    def stop(self) -> None:
        """Stops app server."""
        self._server.stop(0)

    def method(self, name: str):
        """A decorator that is used to register the method for the service invocation.

        Return JSON formatted data response::

            @app.method('start')
            def start(request: InvokeServiceRequest):

                ...

                return json.dumps()

        Return Protocol buffer response::

            @app.method('start')
            def start(request: InvokeServiceRequest):

                ...

                return CustomProtoResponse(data='hello world')


        Specify Response header::

            @app.method('start')
            def start(request: InvokeServiceRequest):

                ...

                resp = InvokeServiceResponse('hello world', 'text/plain')
                resp.headers = ('key', 'value')

                return resp

        Args:
            name (str): name of invoked method
        """
        def decorator(func):
            self._servicer.register_method(name, func)
        return decorator

    def subscribe(self, pubsub_name: str, topic: str, metadata: Optional[Dict[str, str]] = {}):
        """A decorator that is used to register the subscribing topic method.

        The below example registers 'topic' subscription topic and pass custom
        metadata to pubsub component::

            from cloudevents.sdk.event import v1

            @app.subscribe('pubsub_name', 'topic', metadata=(('session-id', 'session-id-value'),))
            def topic(event: v1.Event) -> None:
                ...

        Args:
            pubsub_name (str): the name of the pubsub component
            topic (str): the topic name which is subscribed
            metadata (dict, optional): metadata which will be passed to pubsub component
                during initialization
        """
        def decorator(func):
            self._servicer.register_topic(pubsub_name, topic, func, metadata)
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
