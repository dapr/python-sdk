# -*- coding: utf-8 -*-

"""
Copyright (c) Microsoft Corporation and Dapr Contributors.
Licensed under the MIT License.
"""

import aiohttp

from typing import Callable, Mapping, Dict, Optional, Union, Tuple, TYPE_CHECKING
if TYPE_CHECKING:
    from dapr.serializers import Serializer

from dapr.conf import settings
from dapr.clients.base import DEFAULT_JSON_CONTENT_TYPE
from dapr.clients.exceptions import DaprInternalError, ERROR_CODE_DOES_NOT_EXIST, ERROR_CODE_UNKNOWN

CONTENT_TYPE_HEADER = 'content-type'
DAPR_API_TOKEN_HEADER = 'dapr-api-token'


class DaprHttpClient:
    """A Dapr Http API client"""

    def __init__(self,
                 message_serializer: 'Serializer',
                 timeout: Optional[int] = 60,
                 headers_callback: Optional[Callable[[], Dict[str, str]]] = None):
        """Invokes Dapr over HTTP.

        Args:
            message_serializer (Serializer): Dapr serializer.
            timeout (int, optional): Timeout in seconds, defaults to 60.
            headers_callback (lambda: Dict[str, str]], optional): Generates header for each request.
        """
        self._timeout = aiohttp.ClientTimeout(total=timeout)
        self._serializer = message_serializer
        self._headers_callback = headers_callback

    def get_api_url(self) -> str:
        return 'http://{}:{}/{}'.format(
            settings.DAPR_RUNTIME_HOST,
            settings.DAPR_HTTP_PORT,
            settings.DAPR_API_VERSION)

    async def send_bytes(
            self, method: str, url: str,
            data: Optional[bytes],
            headers: Dict[str, Union[bytes, str]] = {},
            query_params: Optional[Mapping] = None
    ) -> Tuple[bytes, aiohttp.ClientResponse]:
        headers_map = headers
        if not headers_map.get(CONTENT_TYPE_HEADER):
            headers_map[CONTENT_TYPE_HEADER] = DEFAULT_JSON_CONTENT_TYPE

        if settings.DAPR_API_TOKEN is not None:
            headers_map[DAPR_API_TOKEN_HEADER] = settings.DAPR_API_TOKEN

        if self._headers_callback is not None:
            trace_headers = self._headers_callback()
            headers_map.update(trace_headers)

        r = None
        async with aiohttp.ClientSession(timeout=self._timeout) as session:
            r = await session.request(
                method=method,
                url=url,
                data=data,
                headers=headers_map,
                params=query_params)

            if r.status >= 200 and r.status < 300:
                return await r.read(), r

            raise (await self.convert_to_error(r))

    async def convert_to_error(self, response) -> DaprInternalError:
        error_info = None
        try:
            error_body = await response.read()
            if (error_body is None or len(error_body) == 0) and response.status == 404:
                return DaprInternalError("Not Found", ERROR_CODE_DOES_NOT_EXIST)
            error_info = self._serializer.deserialize(error_body)
        except Exception:
            return DaprInternalError(f'Unknown Dapr Error. HTTP status code: {response.status}')

        if error_info and isinstance(error_info, dict):
            message = error_info.get('message')
            error_code = error_info.get('errorCode') or ERROR_CODE_UNKNOWN
            return DaprInternalError(message, error_code)

        return DaprInternalError(f'Unknown Dapr Error. HTTP status code: {response.status}')
