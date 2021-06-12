# -*- coding: utf-8 -*-

"""
Copyright (c) Microsoft Corporation and Dapr Contributors.
Licensed under the MIT License.
"""

import asyncio

from typing import Callable, Dict, Optional, Union

from multidict import MultiDict
from dapr.clients.http.client import DaprHttpClient, CONTENT_TYPE_HEADER
from dapr.clients.grpc._helpers import MetadataTuple, GrpcMessage
from dapr.clients.grpc._response import InvokeMethodResponse
from dapr.serializers import DefaultJSONSerializer


class DaprInvocationHttpClient:
    """Service Invocation HTTP Client"""

    def __init__(
            self,
            timeout: int = 60,
            headers_callback: Optional[Callable[[], Dict[str, str]]] = None):
        """Invokes Dapr's API for method invocation over HTTP.

        Args:
            timeout (int, optional): Timeout in seconds, defaults to 60.
            headers_callback (lambda: Dict[str, str]], optional): Generates header for each request.
        """
        self._client = DaprHttpClient(DefaultJSONSerializer(), timeout, headers_callback)

    def invoke_method(
            self,
            app_id: str,
            method_name: str,
            data: Union[bytes, str, GrpcMessage],
            content_type: Optional[str] = None,
            metadata: Optional[MetadataTuple] = None,
            http_verb: Optional[str] = None,
            http_querystring: Optional[MetadataTuple] = None) -> InvokeMethodResponse:
        """Invoke a service method over HTTP.

        Args:
            app_id (str): Application Id.
            method_name (str): Method to be invoked.
            data (bytes or str or GrpcMessage, optional): Data for requet's body.
            content_type (str, optional): Content type header.
            metadata (MetadataTuple, optional): Additional headers.
            http_verb (str, optional): HTTP verb for the request.
            http_querystring (MetadataTuple, optional): Query parameters.

        Returns:
            InvokeMethodResponse: the response from the method invocation.
        """

        verb = 'GET'
        if http_verb is not None:
            verb = http_verb

        headers = {}
        if metadata is not None:
            for key, value in metadata:
                headers[key] = value
        query_params: MultiDict = MultiDict()
        if http_querystring is not None:
            for key, value in http_querystring:
                query_params.add(key, value)

        if content_type is not None:
            headers[CONTENT_TYPE_HEADER] = content_type

        url = f'{self._client.get_api_url()}/invoke/{app_id}/method/{method_name}'

        if isinstance(data, GrpcMessage):
            body = data.SerializeToString()
        elif isinstance(data, str):
            body = data.encode('utf-8')
        else:
            body = data

        async def make_request():
            resp_body, r = await self._client.send_bytes(
                method=verb,
                headers=headers,
                url=url,
                data=body,
                query_params=query_params)

            resp_data = InvokeMethodResponse(resp_body, r.content_type)
            for key in r.headers:
                resp_data.headers[key] = r.headers.getall(key)  # type: ignore
            return resp_data

        return asyncio.run(make_request())
