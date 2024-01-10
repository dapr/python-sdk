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

from typing import Optional

from dapr.conf import settings


def getAddress(host: Optional[str] = None, port: Optional[str] = None) -> str:
    if not host and not port:
        address = settings.DAPR_GRPC_ENDPOINT or (
            f'{settings.DAPR_RUNTIME_HOST}:' f'{settings.DAPR_GRPC_PORT}'
        )
    else:
        host = host or settings.DAPR_RUNTIME_HOST
        port = port or settings.DAPR_GRPC_PORT
        address = f'{host}:{port}'

    return address
