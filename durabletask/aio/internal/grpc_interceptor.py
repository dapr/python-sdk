# Copyright (c) The Dapr Authors.
# Licensed under the MIT License.

from collections import namedtuple

from grpc import aio as grpc_aio


class _ClientCallDetails(
    namedtuple(
        "_ClientCallDetails",
        ["method", "timeout", "metadata", "credentials", "wait_for_ready", "compression"],
    ),
    grpc_aio.ClientCallDetails,
):
    pass


class DefaultClientInterceptorImpl(
    grpc_aio.UnaryUnaryClientInterceptor,
    grpc_aio.UnaryStreamClientInterceptor,
    grpc_aio.StreamUnaryClientInterceptor,
    grpc_aio.StreamStreamClientInterceptor,
):
    """Async gRPC client interceptor to add metadata to all calls."""

    def __init__(self, metadata: list[tuple[str, str]]):
        super().__init__()
        self._metadata = metadata

    def _intercept_call(
        self, client_call_details: _ClientCallDetails
    ) -> grpc_aio.ClientCallDetails:
        if self._metadata is None:
            return client_call_details

        if client_call_details.metadata is not None:
            metadata = list(client_call_details.metadata)
        else:
            metadata = []

        metadata.extend(self._metadata)
        compression = getattr(client_call_details, "compression", None)
        return _ClientCallDetails(
            client_call_details.method,
            client_call_details.timeout,
            metadata,
            client_call_details.credentials,
            client_call_details.wait_for_ready,
            compression,
        )

    async def intercept_unary_unary(self, continuation, client_call_details, request):
        new_client_call_details = self._intercept_call(client_call_details)
        return await continuation(new_client_call_details, request)

    async def intercept_unary_stream(self, continuation, client_call_details, request):
        new_client_call_details = self._intercept_call(client_call_details)
        return await continuation(new_client_call_details, request)

    async def intercept_stream_unary(self, continuation, client_call_details, request_iterator):
        new_client_call_details = self._intercept_call(client_call_details)
        return await continuation(new_client_call_details, request_iterator)

    async def intercept_stream_stream(self, continuation, client_call_details, request_iterator):
        new_client_call_details = self._intercept_call(client_call_details)
        return await continuation(new_client_call_details, request_iterator)
