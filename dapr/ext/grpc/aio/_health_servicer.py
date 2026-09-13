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

from dapr.ext.grpc._health_servicer import _HealthCheckServicerBase
from dapr.ext.grpc.aio._servicer import _needs_await
from dapr.proto.runtime.v1.appcallback_pb2 import HealthCheckResponse


class _AioHealthCheckServicer(_HealthCheckServicerBase):
    """The asyncio-native implementation of HealthCheck Server.

    Shares registration with the synchronous servicer via their common base; only the gRPC
    entry point differs, awaiting the callback result.
    """

    async def HealthCheck(self, request, context):
        """Health check."""
        health_check = self._require_health_check_cb(context)
        result = health_check()
        if _needs_await(result):
            await result
        return HealthCheckResponse()
