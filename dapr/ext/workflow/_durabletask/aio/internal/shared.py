# Copyright 2026 The Dapr Authors
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#     http://www.apache.org/licenses/LICENSE-2.0
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import logging
from typing import Optional, Sequence, Union

import grpc
from grpc import aio as grpc_aio
from grpc.aio import ChannelArgumentType

from dapr.ext.workflow._durabletask.internal.shared import (
    INSECURE_PROTOCOLS,
    SECURE_PROTOCOLS,
    get_default_host_address,
)

ClientInterceptor = Union[
    grpc_aio.UnaryUnaryClientInterceptor,
    grpc_aio.UnaryStreamClientInterceptor,
    grpc_aio.StreamUnaryClientInterceptor,
    grpc_aio.StreamStreamClientInterceptor,
]

_POLLER_NOISE_MARKER = 'PollerCompletionQueue._handle_events'


class _GrpcAioPollerNoiseFilter(logging.Filter):
    """Drops the harmless grpc.aio poller BlockingIOError (EAGAIN) records.

    The poller does a non-blocking read on its wake-up fd and can get EAGAIN, which
    asyncio logs at ERROR even though the read is retried and nothing is lost.
    """

    def filter(self, record: logging.LogRecord) -> bool:
        exc = record.exc_info[1] if record.exc_info else None
        is_poller_noise = isinstance(exc, BlockingIOError) and (
            _POLLER_NOISE_MARKER in record.getMessage()
        )
        return not is_poller_noise


def _silence_grpc_aio_poller_noise() -> None:
    """Install the poller-noise filter on the asyncio logger if not already present."""
    asyncio_logger = logging.getLogger('asyncio')
    if not any(isinstance(f, _GrpcAioPollerNoiseFilter) for f in asyncio_logger.filters):
        asyncio_logger.addFilter(_GrpcAioPollerNoiseFilter())


def get_grpc_aio_channel(
    host_address: Optional[str],
    secure_channel: bool = False,
    interceptors: Optional[Sequence[ClientInterceptor]] = None,
    options: Optional[ChannelArgumentType] = None,
) -> grpc_aio.Channel:
    """create a grpc asyncio channel

    Args:
        host_address: The host address of the gRPC server. If None, uses the default address.
        secure_channel: Whether to use a secure channel (TLS/SSL). Defaults to False.
        interceptors: Optional sequence of client interceptors to apply to the channel.
        options: Optional sequence of gRPC channel options as (key, value) tuples. Keys defined in https://grpc.github.io/grpc/core/group__grpc__arg__keys.html
    """
    _silence_grpc_aio_poller_noise()

    if host_address is None:
        host_address = get_default_host_address()

    for protocol in SECURE_PROTOCOLS:
        if host_address.lower().startswith(protocol):
            secure_channel = True
            host_address = host_address[len(protocol) :]
            break

    for protocol in INSECURE_PROTOCOLS:
        if host_address.lower().startswith(protocol):
            secure_channel = False
            host_address = host_address[len(protocol) :]
            break

    if secure_channel:
        channel = grpc_aio.secure_channel(
            host_address, grpc.ssl_channel_credentials(), interceptors=interceptors, options=options
        )
    else:
        channel = grpc_aio.insecure_channel(
            host_address, interceptors=interceptors, options=options
        )

    return channel
