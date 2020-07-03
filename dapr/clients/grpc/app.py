# -*- coding: utf-8 -*-

"""
Copyright (c) Microsoft Corporation.
Licensed under the MIT License.
"""
import grpc
import functools

from concurrent import futures
from typing import Dict, Optional

from dapr.clients.grpc._servicier import AppCallbackServicer
from dapr.proto import appcallback_service_v1


class App:
    def __init__(self):
        self._servicer = AppCallbackServicer()
        self._server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
        appcallback_service_v1.add_AppCallbackServicer_to_server(self._servicer, self._server)
        self._server.add_insecure_port('[::]:50051')
    
    def __del__(self):
        self.stop()

    def daprize(self) -> None:
        self._server.start()

    def wait_until_stop(self) -> None:
        self._server.wait_for_termination()

    def stop(self) -> None:
        self._server.stop(0)

    def method(self, name: str):
        def decorator(func):
            self._servicer.register_method(name, func)
        return decorator
    
    def subscriber(self, topic: str, metadata: Optional[Dict[str, str]] = {}):
        def decorator(func):
            self._servicer.register_subscriber(topic, func, metadata)
        return decorator

    def binding(self, name: str):
        def decorator(func):
            self._servicer.register_binding(name, func)
        return decorator
