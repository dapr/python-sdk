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

import os
import grpc

from contextlib import contextmanager
from typing import Optional
from dapr.conf import settings

from dapr.proto.common.v1 import common_pb2 as common_v1
from dapr.proto.runtime.v1 import dapr_pb2 as api_v1
from dapr.proto.runtime.v1 import dapr_pb2_grpc as api_service_v1
from dapr.proto.runtime.v1 import appcallback_pb2 as appcallback_v1
from dapr.proto.runtime.v1 import appcallback_pb2_grpc as appcallback_service_v1


@contextmanager
def connect_dapr(port: Optional[int] = -1):
    if port == -1:
        port = settings.DAPR_GRPC_PORT
    channel = grpc.insecure_channel(f"127.0.0.1:{port}")
    stub = api_service_v1.DaprStub(channel)
    yield stub
    channel.close()


__all__ = [
    'connect_dapr',
    'common_v1',
    'api_v1',
    'appcallback_v1',
    'appcallback_service_v1',
]
