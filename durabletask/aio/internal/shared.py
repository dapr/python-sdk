# Copyright (c) The Dapr Authors.
# Licensed under the MIT License.

from typing import Optional, Sequence, Union

import grpc
from grpc import aio as grpc_aio
from grpc.aio import ChannelArgumentType

from durabletask.internal.shared import (
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
