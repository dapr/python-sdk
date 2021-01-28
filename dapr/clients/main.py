# -*- coding: utf-8 -*-

"""
Copyright (c) Microsoft Corporation.
Licensed under the MIT License.
"""

from typing import Optional, Union
from dapr.clients.exceptions import DaprInternalError
from dapr.clients.grpc.client import DaprGrpcClient, MetadataTuple, InvokeMethodResponse
from dapr.clients.http.dapr_invocation_http_client import DaprInvocationHttpClient
from dapr.conf import settings
from google.protobuf.message import Message as GrpcMessage
from opencensus.trace.tracers.base import Tracer   # type: ignore


class DaprClient(DaprGrpcClient):
    """The Dapr python-sdk uses gRPC for most operations. The exception being
    service invocation which needs to support HTTP to HTTP invocations. The sdk defaults
    to HTTP but can be overridden with the DAPR_API_METHOD_INVOCATION_PROTOCOL environment
    variable. See: https://github.com/dapr/python-sdk/issues/176 for more details"""

    def __init__(self, address: Optional[str] = None, tracer: Optional[Tracer] = None):
        super().__init__(address, tracer)
        self.invocation_client = None

        invocation_protocol = settings.DAPR_API_METHOD_INVOCATION_PROTOCOL.upper()

        if invocation_protocol == 'HTTP':
            self.invocation_client = DaprInvocationHttpClient(tracer=tracer)
        elif invocation_protocol == 'GRPC':
            pass
        else:
            raise DaprInternalError(
                f'Unknown value for DAPR_API_METHOD_INVOCATION_PROTOCOL: {invocation_protocol}')

    def invoke_method(
            self,
            app_id: str,
            method_name: str,
            data: Union[bytes, str, GrpcMessage],
            content_type: Optional[str] = None,
            metadata: Optional[MetadataTuple] = None,
            http_verb: Optional[str] = None,
            http_querystring: Optional[MetadataTuple] = None) -> InvokeMethodResponse:

        if self.invocation_client:
            return self.invocation_client.invoke_method(
                app_id,
                method_name,
                data,
                content_type=content_type,
                metadata=metadata,
                http_verb=http_verb,
                http_querystring=http_querystring)
        else:
            return super().invoke_method(
                app_id,
                method_name,
                data,
                content_type=content_type,
                metadata=metadata,
                http_verb=http_verb,
                http_querystring=http_querystring)
