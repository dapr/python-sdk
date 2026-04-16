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

from collections import namedtuple

import grpc


class _ClientCallDetails(
    namedtuple(
        '_ClientCallDetails',
        ['method', 'timeout', 'metadata', 'credentials', 'wait_for_ready', 'compression'],
    ),
    grpc.ClientCallDetails,
):
    """This is an implementation of the ClientCallDetails interface needed for interceptors.
    This class takes six named values and inherits the ClientCallDetails from grpc package.
    This class encloses the values that describe a RPC to be invoked.
    """

    pass


class DefaultClientInterceptorImpl(
    grpc.UnaryUnaryClientInterceptor,
    grpc.UnaryStreamClientInterceptor,
    grpc.StreamUnaryClientInterceptor,
    grpc.StreamStreamClientInterceptor,
):
    """The class implements a UnaryUnaryClientInterceptor, UnaryStreamClientInterceptor,
    StreamUnaryClientInterceptor and StreamStreamClientInterceptor from grpc to add an
    interceptor to add additional headers to all calls as needed."""

    def __init__(self, metadata: list[tuple[str, str]]):
        super().__init__()
        self._metadata = metadata

    def _intercept_call(self, client_call_details: _ClientCallDetails) -> grpc.ClientCallDetails:
        """Internal intercept_call implementation which adds metadata to grpc metadata in the RPC
        call details."""
        if self._metadata is None:
            return client_call_details

        if client_call_details.metadata is not None:
            metadata = list(client_call_details.metadata)
        else:
            metadata = []

        metadata.extend(self._metadata)
        client_call_details = _ClientCallDetails(
            client_call_details.method,
            client_call_details.timeout,
            metadata,
            client_call_details.credentials,
            client_call_details.wait_for_ready,
            client_call_details.compression,
        )

        return client_call_details

    def intercept_unary_unary(self, continuation, client_call_details, request):
        new_client_call_details = self._intercept_call(client_call_details)
        return continuation(new_client_call_details, request)

    def intercept_unary_stream(self, continuation, client_call_details, request):
        new_client_call_details = self._intercept_call(client_call_details)
        return continuation(new_client_call_details, request)

    def intercept_stream_unary(self, continuation, client_call_details, request):
        new_client_call_details = self._intercept_call(client_call_details)
        return continuation(new_client_call_details, request)

    def intercept_stream_stream(self, continuation, client_call_details, request):
        new_client_call_details = self._intercept_call(client_call_details)
        return continuation(new_client_call_details, request)
