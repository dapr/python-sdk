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

from typing import Callable, Dict, List, Optional, Union
from warnings import warn

from dapr.clients.base import DaprActorClientBase
from dapr.clients.exceptions import DaprInternalError, ERROR_CODE_UNKNOWN
from dapr.clients.grpc.client import DaprGrpcClient, MetadataTuple, InvokeMethodResponse
from dapr.clients.http.dapr_actor_http_client import DaprActorHttpClient
from dapr.clients.http.dapr_invocation_http_client import DaprInvocationHttpClient
from dapr.clients.retry import RetryPolicy
from dapr.conf import settings
from google.protobuf.message import Message as GrpcMessage


__all__ = [
    'DaprClient',
    'DaprActorClientBase',
    'DaprActorHttpClient',
    'DaprInternalError',
    'ERROR_CODE_UNKNOWN',
]


from grpc import (  # type: ignore
    UnaryUnaryClientInterceptor,
    UnaryStreamClientInterceptor,
    StreamUnaryClientInterceptor,
    StreamStreamClientInterceptor,
)


class DaprClient(DaprGrpcClient):
    """The Dapr python-sdk uses gRPC for most operations. The exception being
    service invocation which needs to support HTTP to HTTP invocations. The sdk defaults
    to HTTP but can be overridden with the DAPR_API_METHOD_INVOCATION_PROTOCOL environment
    variable. See: https://github.com/dapr/python-sdk/issues/176 for more details"""

    def __init__(
        self,
        address: Optional[str] = None,
        headers_callback: Optional[Callable[[], Dict[str, str]]] = None,
        interceptors: Optional[
            List[
                Union[
                    UnaryUnaryClientInterceptor,
                    UnaryStreamClientInterceptor,
                    StreamUnaryClientInterceptor,
                    StreamStreamClientInterceptor,
                ]
            ]
        ] = None,
        http_timeout_seconds: Optional[int] = None,
        max_grpc_message_length: Optional[int] = None,
        retry_policy: Optional[RetryPolicy] = None,
    ):
        """Connects to Dapr Runtime via gRPC and HTTP.

        Args:
            address (str, optional): Dapr Runtime gRPC endpoint address.
            headers_callback (lambda: Dict[str, str], optional): Generates header for each request.
            interceptors (list of UnaryUnaryClientInterceptor or
                UnaryStreamClientInterceptor or
                StreamUnaryClientInterceptor or
                StreamStreamClientInterceptor, optional): gRPC interceptors.
            http_timeout_seconds (int): specify a timeout for http connections
            max_grpc_message_length (int, optional): The maximum grpc send and receive
                message length in bytes.
        """
        super().__init__(address, interceptors, max_grpc_message_length, retry_policy)
        self.invocation_client = None

        invocation_protocol = settings.DAPR_API_METHOD_INVOCATION_PROTOCOL.upper()

        if invocation_protocol == 'HTTP':
            if http_timeout_seconds is None:
                http_timeout_seconds = settings.DAPR_HTTP_TIMEOUT_SECONDS
            self.invocation_client = DaprInvocationHttpClient(
                headers_callback=headers_callback, timeout=http_timeout_seconds
            )
        elif invocation_protocol == 'GRPC':
            pass
        else:
            raise DaprInternalError(
                f'Unknown value for DAPR_API_METHOD_INVOCATION_PROTOCOL: {invocation_protocol}'
            )

    def invoke_method(
        self,
        app_id: str,
        method_name: str,
        data: Union[bytes, str, GrpcMessage] = '',
        content_type: Optional[str] = None,
        metadata: Optional[MetadataTuple] = None,
        http_verb: Optional[str] = None,
        http_querystring: Optional[MetadataTuple] = None,
        timeout: Optional[int] = None,
    ) -> InvokeMethodResponse:
        """Invoke a service method over gRPC or HTTP.

        Args:
            app_id (str): Application ID.
            method_name (str): Method to be invoked.
            data (bytes or str or GrpcMessage, optional): Data for request's body.
            content_type (str, optional): Content type of the data.
            metadata (MetadataTuple, optional): Additional metadata or headers.
            http_verb (str, optional): HTTP verb for the request.
            http_querystring (MetadataTuple, optional): Query parameters.
            timeout (int, optional): request timeout in seconds.

        Returns:
            InvokeMethodResponse: the response from the method invocation.
        """
        if self.invocation_client:
            return self.invocation_client.invoke_method(
                app_id,
                method_name,
                data,
                content_type=content_type,
                metadata=metadata,
                http_verb=http_verb,
                http_querystring=http_querystring,
                timeout=timeout,
            )
        else:
            return super().invoke_method(
                app_id,
                method_name,
                data,
                content_type=content_type,
                metadata=metadata,
                http_verb=http_verb,
                http_querystring=http_querystring,
                timeout=timeout,
            )

    async def invoke_method_async(
        self,
        app_id: str,
        method_name: str,
        data: Union[bytes, str, GrpcMessage],
        content_type: Optional[str] = None,
        metadata: Optional[MetadataTuple] = None,
        http_verb: Optional[str] = None,
        http_querystring: Optional[MetadataTuple] = None,
        timeout: Optional[int] = None,
    ) -> InvokeMethodResponse:
        """Invoke a service method over gRPC or HTTP.

        Args:
            app_id (str): Application ID.
            method_name (str): Method to be invoked.
            data (bytes or str or GrpcMessage, optional): Data for request's body.
            content_type (str, optional): Content type of the data.
            metadata (MetadataTuple, optional): Additional metadata or headers.
            http_verb (str, optional): HTTP verb for the request.
            http_querystring (MetadataTuple, optional): Query parameters.
            timeout (int, optional): Request timeout in seconds.

        Returns:
            InvokeMethodResponse: the method invocation response.
        """
        if self.invocation_client:
            warn(
                'Async invocation is deprecated. Please use `dapr.aio.clients.DaprClient`.',
                DeprecationWarning,
                stacklevel=2,
            )
            return await self.invocation_client.invoke_method_async(
                app_id,
                method_name,
                data,
                content_type=content_type,
                metadata=metadata,
                http_verb=http_verb,
                http_querystring=http_querystring,
                timeout=timeout,
            )
        else:
            raise NotImplementedError(
                'Please use `dapr.aio.clients.DaprClient` for async invocation'
            )
