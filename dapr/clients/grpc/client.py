# -*- coding: utf-8 -*-

"""
Copyright (c) Microsoft Corporation.
Licensed under the MIT License.
"""

import grpc  # type: ignore

from typing import Optional, Union

from google.protobuf.message import Message as GrpcMessage

from dapr.conf import settings
from dapr.proto import api_v1, api_service_v1, common_v1

from dapr.clients.grpc._helpers import MetadataTuple, HeaderInterceptor
from dapr.clients.grpc._request import InvokeServiceRequestData
from dapr.clients.grpc._response import InvokeServiceResponse


class DaprClient:
    """The convenient layer implementation of Dapr gRPC APIs.

    This provides the wrappers and helpers to allows developers to use Dapr runtime gRPC API
    easily and consistently.

    Examples:

        >>> import dapr
        >>> d = dapr.DaprClient()
        >>> resp = d.invoke_service('callee', 'method', b'data')

    With context manager:

        >>> import dapr
        >>> with dapr.DaprClient() as d:
        ...     resp = d.invoke_service('callee', 'method', b'data')
    """

    def __init__(self, address: Optional[str] = None):
        """Connects to Dapr Runtime and initialize gRPC client stub.

        Args:
            address (str, optional): Dapr Runtime gRPC endpoint address.
        """
        if not address:
            address = f"{settings.DAPR_RUNTIME_HOST}:{settings.DAPR_GRPC_PORT}"
        self._channel = grpc.insecure_channel(address)

        if settings.DAPR_API_TOKEN:
            api_token_interceptor = HeaderInterceptor([
                ('dapr-api-token', settings.DAPR_API_TOKEN), ])
            self._channel = grpc.intercept_channel(self._channel, api_token_interceptor)

        self._stub = api_service_v1.DaprStub(self._channel)

    def close(self):
        """Closes Dapr runtime gRPC channel."""
        self._channel.close()

    def __del__(self):
        self.close()

    def __enter__(self) -> 'DaprClient':
        return self

    def __exit__(self, exc_type, exc_value, traceback) -> None:
        self.close()

    def _get_http_extension(
            self, http_verb: str,
            http_querystring: Optional[MetadataTuple] = ()
    ) -> common_v1.HTTPExtension:  # type: ignore
        verb = common_v1.HTTPExtension.Verb.Value(http_verb)  # type: ignore
        http_ext = common_v1.HTTPExtension(verb=verb)
        for key, val in http_querystring:  # type: ignore
            http_ext.querystring[key] = val
        return http_ext

    def invoke_service(
            self,
            id: str,
            method: str,
            data: Union[bytes, str, GrpcMessage],
            content_type: Optional[str] = None,
            metadata: Optional[MetadataTuple] = None,
            http_verb: Optional[str] = None,
            http_querystring: Optional[MetadataTuple] = None) -> InvokeServiceResponse:
        """Invokes the target service to call method.

        This can invoke the specified target service to call method with bytes array data or
        custom protocol buffer message. If your callee application uses http appcallback,
        http_verb and http_querystring must be specified. Otherwise, Dapr runtime will return
        error.

        The example calls `callee` service with bytes data, which implements grpc appcallback:

            from dapr import DaprClient

            with DaprClient() as d:
                resp = d.invoke_service(
                    id='callee',
                    method='method',
                    data=b'message',
                    content_type='text/plain',
                    metadata=(
                        ('header1', 'value1')
                    ),
                )

                # resp.content includes the content in bytes.
                # resp.content_type specifies the content type of resp.content.
                # Thus, resp.content can be deserialized properly.

        When sending custom protocol buffer message object, it doesn't requires content_type:

            from dapr import DaprClient

            req_data = dapr_example_v1.CustomRequestMessage(data='custom')

            with DaprClient() as d:
                resp = d.invoke_service(
                    id='callee',
                    method='method',
                    data=req_data,
                    metadata=(
                        ('header1', 'value1')
                    ),
                )
                # Create protocol buffer object
                resp_data = dapr_example_v1.CustomResponseMessage()
                # Deserialize to resp_data
                resp.unpack(resp_data)

        The example calls `callee` service which implements http appcallback:

            from dapr import DaprClient

            with DaprClient() as d:
                resp = d.invoke_service(
                    id='callee',
                    method='method',
                    data=b'message',
                    content_type='text/plain',
                    metadata=(
                        ('header1', 'value1')
                    ),
                    http_verb='POST',
                    http_querystring=(
                        ('key1', 'value1')
                    ),
                )

                # resp.content includes the content in bytes.
                # resp.content_type specifies the content type of resp.content.
                # Thus, resp.content can be deserialized properly.

        Args:
            id (str): the callee app id
            method (str): the method name which is called
            data (bytes or :obj:`google.protobuf.message.Message`): bytes or Message for data
                which will send to id
            metadata (tuple, optional): custom metadata
            http_verb (str, optional): http method verb to call HTTP callee application
            http_querystring (tuple, optional): the tuple to represent query string

        Returns:
            :class:`InvokeServiceResponse` object returned from callee
        """
        req_data = InvokeServiceRequestData(data, content_type)

        http_ext = None
        if http_verb:
            http_ext = self._get_http_extension(http_verb, http_querystring)

        req = api_v1.InvokeServiceRequest(
            id=id,
            message=common_v1.InvokeRequest(
                method=method,
                data=req_data.data,
                content_type=req_data.content_type,
                http_extension=http_ext)
        )

        response, call = self._stub.InvokeService.with_call(req, metadata=metadata)

        return InvokeServiceResponse(
            response.data, response.content_type,
            call.initial_metadata(), call.trailing_metadata())
