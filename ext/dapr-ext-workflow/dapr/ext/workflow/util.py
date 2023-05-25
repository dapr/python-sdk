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

from typing import Union
from dapr.conf import settings


def getAddress(host: Union[str, None] = None, port: Union[str, None] = None) -> str:
    if host is None:
            host = settings.DAPR_RUNTIME_HOST
    if not host or len(host) == 0 or len(host.strip()) == 0:
        host = "localhost"
    port = port or settings.DAPR_GRPC_PORT
    address = f"{host}:{port}"
    return address