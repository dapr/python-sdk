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

from typing import Any, Optional, Sequence

from dapr.conf import settings


def get_grpc_channel_options(
    max_grpc_message_length: Optional[int] = None,
) -> Optional[Sequence[tuple[str, Any]]]:
    """Resolves gRPC channel options for the workflow message-size limit.

    Resolution order: the explicit ``max_grpc_message_length`` kwarg, then
    ``settings.DAPR_GRPC_MAX_INBOUND_MESSAGE_SIZE_BYTES``, else ``None``.

    Sets BOTH send and receive limits symmetrically because workflow activity
    payloads cross the channel in both directions. ``None`` is returned when no
    limit is configured, preserving the gRPC default behavior.

    Args:
        max_grpc_message_length: Explicit max gRPC message size in bytes. Takes
            precedence over the env-var setting when truthy.

    Returns:
        A sequence of ``(option, value)`` tuples setting both send and receive
        limits, or ``None`` when no limit is configured.
    """
    size = max_grpc_message_length or settings.DAPR_GRPC_MAX_INBOUND_MESSAGE_SIZE_BYTES
    if not size:
        return None
    return [
        ('grpc.max_send_message_length', size),
        ('grpc.max_receive_message_length', size),
    ]


def getAddress(host: Optional[str] = None, port: Optional[str] = None) -> str:
    if not host and not port:
        address = settings.DAPR_GRPC_ENDPOINT or (
            f'{settings.DAPR_RUNTIME_HOST}:{settings.DAPR_GRPC_PORT}'
        )
    else:
        host = host or settings.DAPR_RUNTIME_HOST
        port = port or settings.DAPR_GRPC_PORT
        address = f'{host}:{port}'

    return address
