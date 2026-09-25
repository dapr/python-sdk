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

    Precedence: explicit ``max_grpc_message_length`` kwarg (if non-zero),
    else ``settings.DAPR_GRPC_MAX_INBOUND_MESSAGE_SIZE_BYTES`` (if non-zero),
    else the gRPC default. A ``0`` in either source is interpreted as
    "no opinion / use default" and falls through to the next source — this
    matches ``global_settings.DAPR_GRPC_MAX_INBOUND_MESSAGE_SIZE_BYTES = 0``
    being the documented "unset" sentinel.

    Sets BOTH send and receive limits symmetrically because workflow activity
    payloads cross the channel in both directions. Returns ``None`` when no
    explicit limit is configured so callers leave the channel unconfigured and
    the gRPC default applies.

    Args:
        max_grpc_message_length: Explicit max gRPC message size in bytes.
            ``0`` or ``None`` means "no opinion" and falls through to the
            env var.

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
