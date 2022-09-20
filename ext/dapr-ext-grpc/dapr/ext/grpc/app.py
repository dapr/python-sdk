# -*- coding: utf-8 -*-

"""
Copyright 2021 The Dapr Authors
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

import grpc

from concurrent import futures
from typing import Dict, Optional

from dapr.conf import settings
from dapr.ext.grpc._servicier import _CallbackServicer, Rule   # type: ignore
from dapr.proto import appcallback_service_v1


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
            max_grpc_messsage_length (int, optional): The maximum grpc send and receive
                message length in bytes. Only used when kwargs are not set.
            kwargs: arguments to grpc.server()
        """
        self._servicer = _CallbackServicer()
        if not kwargs:
            options = []
            if max_grpc_message_length is not None:
                options = [
                    ('grpc.max_send_message_length', max_grpc_message_length),
                    ('grpc.max_receive_message_length', max_grpc_message_length)]
            self._server = grpc.server(  # type: ignore
                futures.ThreadPoolExecutor(max_workers=10), options=options)
        else:
            self._server = grpc.server(**kwargs)  # type: ignore
        appcallback_service_v1.add_AppCallbackServicer_to_server(self._servicer, self._server)

    def __del__(self):
        self.stop()

    def add_external_service(self, servicer_callback, external_servicer):
        """Adds an external gRPC service to the same server"""
        servicer_callback(external_servicer, self._server)

    def run(self, app_port: Optional[int] = None) -> None:
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

    def subscribe(self, pubsub_name: str, topic: str, metadata: Optional[Dict[str, str]] = {},
                  rule: Optional[Rule] = None, disable_topic_validation: Optional[bool] = False):
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
            self._servicer.register_topic(pubsub_name, topic, func, metadata, rule,
                                          disable_topic_validation)
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
