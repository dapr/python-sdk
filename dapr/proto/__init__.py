# -*- coding: utf-8 -*-

"""
Copyright (c) Microsoft Corporation and Dapr Contributors.
Licensed under the MIT License.
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
