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

from collections import namedtuple
from typing import List, Tuple

from grpc.aio import UnaryUnaryClientInterceptor, ClientCallDetails  # type: ignore

from dapr.conf import settings


class _ClientCallDetailsAsync(
    namedtuple(
        '_ClientCallDetails', ['method', 'timeout', 'metadata', 'credentials', 'wait_for_ready']
    ),
    ClientCallDetails,
):
    """This is an implementation of the ClientCallDetails interface needed for interceptors.
    This class takes five named values and inherits the ClientCallDetails from grpc package.
    This class encloses the values that describe a RPC to be invoked.
    """

    pass


class DaprClientTimeoutInterceptorAsync(UnaryUnaryClientInterceptor):
    def intercept_unary_unary(self, continuation, client_call_details, request):
        # If a specific timeout is not set, create a new ClientCallDetails with the default timeout
        if client_call_details.timeout is None:
            new_client_call_details = _ClientCallDetailsAsync(
                client_call_details.method,
                settings.DAPR_API_TIMEOUT_SECONDS,
                client_call_details.metadata,
                client_call_details.credentials,
                client_call_details.wait_for_ready,
            )
            return continuation(new_client_call_details, request)

        return continuation(client_call_details, request)


class DaprClientInterceptorAsync(UnaryUnaryClientInterceptor):
    """The class implements a UnaryUnaryClientInterceptor from grpc to add an interceptor to add
    additional headers to all calls as needed.

    Examples:

        interceptor = HeaderInterceptor([('header', 'value', )])
        intercepted_channel = grpc.intercept_channel(grpc_channel, interceptor)

    With multiple header values:

        interceptor = HeaderInterceptor([('header1', 'value1', ), ('header2', 'value2', )])
        intercepted_channel = grpc.intercept_channel(grpc_channel, interceptor)
    """

    def __init__(self, metadata: List[Tuple[str, str]]):
        """Initializes the metadata field for the class.

        Args:
            metadata list[tuple[str, str]]: list of tuple of (key, value) strings
            representing header values
        """

        self._metadata = metadata

    async def _intercept_call(self, client_call_details: ClientCallDetails) -> ClientCallDetails:
        """Internal intercept_call implementation which adds metadata to grpc metadata in the RPC
        call details.

        Args:
            client_call_details :class: `ClientCallDetails`: object that describes a RPC
            to be invoked

        Returns:
            :class: `ClientCallDetails` modified call details
        """

        metadata = []
        if client_call_details.metadata is not None:
            metadata = list(client_call_details.metadata)
        metadata.extend(self._metadata)

        new_call_details = _ClientCallDetailsAsync(
            client_call_details.method,
            client_call_details.timeout,
            metadata,
            client_call_details.credentials,
            client_call_details.wait_for_ready,
        )
        return new_call_details

    async def intercept_unary_unary(self, continuation, client_call_details, request):
        """This method intercepts a unary-unary gRPC call. This is the implementation of the
        abstract method defined in UnaryUnaryClientInterceptor defined in grpc. This is invoked
        automatically by grpc based on the order in which interceptors are added to the channel.

        Args:
            continuation: a callable to be invoked to continue with the RPC or next interceptor
            client_call_details: a ClientCallDetails object describing the outgoing RPC
            request: the request value for the RPC

        Returns:
            A response object after invoking the continuation callable
        """

        # Pre-process or intercept call
        new_call_details = await self._intercept_call(client_call_details)
        # Call continuation
        response = await continuation(new_call_details, request)
        return response
