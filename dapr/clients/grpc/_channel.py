# -*- coding: utf-8 -*-

"""
Copyright 2026 The Dapr Authors
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

from typing import Any, List, Optional, Sequence, Tuple

import grpc.aio  # type: ignore

from dapr.clients.exceptions import DaprInternalError
from dapr.conf import settings
from dapr.conf.helpers import GrpcEndpoint
from dapr.version import __version__


def resolve_grpc_endpoint(address: Optional[str] = None) -> GrpcEndpoint:
    """Resolves the daprd gRPC endpoint from an explicit address or settings.

    Resolution order: the ``address`` argument, ``DAPR_GRPC_ENDPOINT``, then
    ``DAPR_RUNTIME_HOST``:``DAPR_GRPC_PORT``.
    """
    if not address:
        address = settings.DAPR_GRPC_ENDPOINT or (
            f'{settings.DAPR_RUNTIME_HOST}:{settings.DAPR_GRPC_PORT}'
        )
    try:
        return GrpcEndpoint(address)
    except ValueError as error:
        raise DaprInternalError(f'{error}') from error


def create_aio_channel(
    address: Optional[str] = None,
    *,
    interceptors: Optional[Sequence[grpc.aio.ClientInterceptor]] = None,
    max_grpc_message_length: Optional[int] = None,
    credentials: Optional[grpc.ChannelCredentials] = None,
) -> grpc.aio.Channel:
    """Creates a grpc.aio channel to daprd with the SDK's standard options.

    Single home for the channel setup shared by ``DaprGrpcClientAsync``,
    ``DaprActorGrpcClient`` and ``ActorGrpcHost``: address resolution, the SDK
    user agent, message-size limits, the per-call timeout interceptor and the
    API token interceptor when configured.

    Args:
        address (str, optional): daprd gRPC address; resolved via
            :func:`resolve_grpc_endpoint` when omitted.
        interceptors (Sequence, optional): extra client interceptors, applied
            before the SDK's timeout and API token interceptors.
        max_grpc_message_length (int, optional): caps send and receive message
            sizes; when omitted ``DAPR_GRPC_MAX_INBOUND_MESSAGE_SIZE_BYTES``
            caps only the receive size.
        credentials (grpc.ChannelCredentials, optional): TLS credentials used
            when the endpoint requires TLS; defaults to the system SSL ones.
    """
    # imported lazily: dapr.aio.clients imports DaprGrpcClientAsync, which imports this module
    from dapr.aio.clients.grpc.interceptors import (
        DaprClientInterceptorAsync,
        DaprClientTimeoutInterceptorAsync,
    )

    useragent = f'dapr-sdk-python/{__version__}'
    options: List[Tuple[str, Any]] = [('grpc.primary_user_agent', useragent)]
    if max_grpc_message_length:
        options.append(('grpc.max_send_message_length', max_grpc_message_length))
        options.append(('grpc.max_receive_message_length', max_grpc_message_length))
    elif settings.DAPR_GRPC_MAX_INBOUND_MESSAGE_SIZE_BYTES:
        options.append(
            (
                'grpc.max_receive_message_length',
                settings.DAPR_GRPC_MAX_INBOUND_MESSAGE_SIZE_BYTES,
            )
        )

    uri = resolve_grpc_endpoint(address)

    channel_interceptors: List[grpc.aio.ClientInterceptor] = list(interceptors or [])
    channel_interceptors.append(DaprClientTimeoutInterceptorAsync())
    if settings.DAPR_API_TOKEN:
        channel_interceptors.append(
            DaprClientInterceptorAsync([('dapr-api-token', settings.DAPR_API_TOKEN)])
        )

    if uri.tls:
        return grpc.aio.secure_channel(
            uri.endpoint,
            credentials=credentials or grpc.ssl_channel_credentials(),  # type: ignore[attr-defined]
            options=options,
            interceptors=channel_interceptors,
        )
    return grpc.aio.insecure_channel(uri.endpoint, options, interceptors=channel_interceptors)
