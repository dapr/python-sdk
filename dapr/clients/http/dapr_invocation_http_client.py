# -*- coding: utf-8 -*-

"""
Copyright 2021 The Dapr Authors
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

import asyncio

from typing import Callable, Dict, Optional, Union

from multidict import MultiDict
from dapr.clients.http.client import DaprHttpClient, CONTENT_TYPE_HEADER
from dapr.clients.grpc._helpers import MetadataTuple, GrpcMessage
from dapr.clients.grpc._response import InvokeMethodResponse
from dapr.serializers import DefaultJSONSerializer
from dapr.version import __version__

USER_AGENT_HEADER = 'User-Agent'
DAPR_USER_AGENT = f'dapr-python-sdk/{__version__}'


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

    async def invoke_method_async(
            self,
            app_id: str,
            method_name: str,
            data: Union[bytes, str, GrpcMessage],
            content_type: Optional[str] = None,
            metadata: Optional[MetadataTuple] = None,
            http_verb: Optional[str] = None,
            http_querystring: Optional[MetadataTuple] = None,
            timeout: Optional[int] = None) -> InvokeMethodResponse:
        """Invoke a service method over HTTP (async).

        Args:
            app_id (str): Application Id.
            method_name (str): Method to be invoked.
            data (bytes or str or GrpcMessage, optional): Data for requet's body.
            content_type (str, optional): Content type header.
            metadata (MetadataTuple, optional): Additional headers.
            http_verb (str, optional): HTTP verb for the request.
            http_querystring (MetadataTuple, optional): Query parameters.
            timeout (int, optional): request timeout in seconds.

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

        headers[USER_AGENT_HEADER] = DAPR_USER_AGENT

        url = f'{self._client.get_api_url()}/invoke/{app_id}/method/{method_name}'

        if isinstance(data, GrpcMessage):
            body = data.SerializeToString()
        elif isinstance(data, str):
            body = data.encode('utf-8')
        else:
            body = data

        async def make_request() -> InvokeMethodResponse:
            resp_body, r = await self._client.send_bytes(
                method=verb,
                headers=headers,
                url=url,
                data=body,
                query_params=query_params,
                timeout=timeout)

            resp_data = InvokeMethodResponse(resp_body, r.content_type)
            respHeaders = resp_data.headers
            for key in r.headers:
                respHeaders[key] = r.headers[key]  # type: ignore

            headerTuples = [(k, v) for k, v in respHeaders.items()]
            resp_data.headers = headerTuples  # type: ignore
            return resp_data
        return await make_request()

    def invoke_method(
        self,
        app_id: str,
        method_name: str,
        data: Union[bytes, str, GrpcMessage],
        content_type: Optional[str] = None,
        metadata: Optional[MetadataTuple] = None,
        http_verb: Optional[str] = None,
        http_querystring: Optional[MetadataTuple] = None,
        timeout: Optional[int] = None
    ) -> InvokeMethodResponse:
        """Invoke a service method over HTTP (async).

        Args:
            app_id (str): Application Id.
            method_name (str): Method to be invoked.
            data (bytes or str or GrpcMessage, optional): Data for requet's body.
            content_type (str, optional): Content type header.
            metadata (MetadataTuple, optional): Additional headers.
            http_verb (str, optional): HTTP verb for the request.
            http_querystring (MetadataTuple, optional): Query parameters.
            timeout (int, optional): request timeout in seconds.

        Returns:
            InvokeMethodResponse: the response from the method invocation.
        """

        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        awaitable = self.invoke_method_async(
            app_id,
            method_name,
            data,
            content_type,
            metadata,
            http_verb,
            http_querystring,
            timeout)
        return loop.run_until_complete(awaitable)
