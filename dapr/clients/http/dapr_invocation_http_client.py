# -*- coding: utf-8 -*-

"""
Copyright (c) Microsoft Corporation.
Licensed under the MIT License.
"""

import asyncio

from typing import Optional, Union

from dapr.clients.http.client import DaprHttpClient, CONTENT_TYPE_HEADER
from dapr.clients.grpc._helpers import MetadataTuple, GrpcMessage
from dapr.clients.grpc._response import InvokeMethodResponse
from dapr.serializers import DefaultJSONSerializer
from opencensus.trace.tracers.base import Tracer   # type: ignore


class DaprInvocationHttpClient:
    """Service Invocation HTTP Client"""

    def __init__(self, timeout: int = 60, tracer: Optional[Tracer] = None):
        self._client = DaprHttpClient(DefaultJSONSerializer(), timeout, tracer)

    def invoke_method(
            self,
            app_id: str,
            method_name: str,
            data: Union[bytes, str, GrpcMessage],
            content_type: Optional[str] = None,
            metadata: Optional[MetadataTuple] = None,
            http_verb: Optional[str] = None,
            http_querystring: Optional[MetadataTuple] = None) -> InvokeMethodResponse:
        """This implementation is designed to seemlessly mimic the behavior of the grpc
        service invoke implementation. Please see the grpc version for parameter definitions
        and samples"""

        verb = 'GET'
        if http_verb is not None:
            verb = http_verb

        headers = {}
        if metadata is not None:
            for key, value in metadata:
                headers[key] = value
        query_params = {}
        if http_querystring is not None:
            for key, value in http_querystring:
                query_params[key] = value

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
