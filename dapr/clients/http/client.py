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

import aiohttp

from typing import Callable, Mapping, Dict, Optional, Union, Tuple, TYPE_CHECKING

from dapr.clients.health import DaprHealth
from dapr.clients.http.conf import (
    DAPR_API_TOKEN_HEADER,
    USER_AGENT_HEADER,
    DAPR_USER_AGENT,
    CONTENT_TYPE_HEADER,
)
from dapr.clients.retry import RetryPolicy

if TYPE_CHECKING:
    from dapr.serializers import Serializer

from dapr.conf import settings
from dapr.clients.base import DEFAULT_JSON_CONTENT_TYPE
from dapr.clients.exceptions import DaprInternalError, ERROR_CODE_DOES_NOT_EXIST, ERROR_CODE_UNKNOWN


class DaprHttpClient:
    """A Dapr Http API client"""

    def __init__(
        self,
        message_serializer: 'Serializer',
        timeout: Optional[int] = 60,
        headers_callback: Optional[Callable[[], Dict[str, str]]] = None,
        retry_policy: Optional[RetryPolicy] = None,
    ):
        """Invokes Dapr over HTTP.

        Args:
            message_serializer (Serializer): Dapr serializer.
            timeout (int, optional): Timeout in seconds, defaults to 60.
            headers_callback (lambda: Dict[str, str]], optional): Generates header for each request.
        """
        DaprHealth.wait_until_ready()

        self._timeout = aiohttp.ClientTimeout(total=timeout)
        self._serializer = message_serializer
        self._headers_callback = headers_callback
        self.retry_policy = retry_policy or RetryPolicy()

    async def send_bytes(
        self,
        method: str,
        url: str,
        data: Optional[bytes],
        headers: Dict[str, Union[bytes, str]] = {},
        query_params: Optional[Mapping] = None,
        timeout: Optional[int] = None,
    ) -> Tuple[bytes, aiohttp.ClientResponse]:
        headers_map = headers
        if not headers_map.get(CONTENT_TYPE_HEADER):
            headers_map[CONTENT_TYPE_HEADER] = DEFAULT_JSON_CONTENT_TYPE

        if settings.DAPR_API_TOKEN is not None:
            headers_map[DAPR_API_TOKEN_HEADER] = settings.DAPR_API_TOKEN

        if self._headers_callback is not None:
            trace_headers = self._headers_callback()
            headers_map.update(trace_headers)

        headers_map[USER_AGENT_HEADER] = DAPR_USER_AGENT

        r = None
        client_timeout = aiohttp.ClientTimeout(total=timeout) if timeout else self._timeout
        sslcontext = self.get_ssl_context()

        async with aiohttp.ClientSession() as session:
            req = {
                'method': method,
                'url': url,
                'data': data,
                'headers': headers_map,
                'sslcontext': sslcontext,
                'params': query_params,
                'timeout': client_timeout,
            }
            r = await self.retry_policy.make_http_call(session, req)

            if 200 <= r.status < 300:
                return await r.read(), r

            raise (await self.convert_to_error(r))

    async def convert_to_error(self, response: aiohttp.ClientResponse) -> DaprInternalError:
        error_info = None
        try:
            error_body = await response.read()
            if (error_body is None or len(error_body) == 0) and response.status == 404:
                return DaprInternalError('Not Found', ERROR_CODE_DOES_NOT_EXIST)
            error_info = self._serializer.deserialize(error_body)
        except Exception:
            return DaprInternalError(
                f'Unknown Dapr Error. HTTP status code: {response.status}',
                raw_response_bytes=error_body,
            )

        if error_info and isinstance(error_info, dict):
            message = error_info.get('message')
            error_code = error_info.get('errorCode') or ERROR_CODE_UNKNOWN
            return DaprInternalError(message, error_code, raw_response_bytes=error_body)

        return DaprInternalError(
            f'Unknown Dapr Error. HTTP status code: {response.status}',
            raw_response_bytes=error_body,
        )

    def get_ssl_context(self):
        # This method is used (overwritten) from tests
        # to return context for self-signed certificates
        return False
