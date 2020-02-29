# -*- coding: utf-8 -*-

"""
Copyright (c) Microsoft Corporation.
Licensed under the MIT License.
"""
import aiohttp
import asyncio
import io

from dapr.conf import settings
from dapr.clients.base import DaprActorClientBase

_DEFAULT_ENCODING='utf-8'
_DEFAULT_CONTENT_TYPE='application/octet-stream'
_DEFAULT_JSON_CONTENT_TYPE=f'application/json; charset={_DEFAULT_ENCODING}'

class DaprActorHttpClient(DaprActorClientBase):
    """A Dapr Actor http client implementing :class:`DaprActorClientBase`"""

    def __init__(self, timeout=60):
        self._timeout = aiohttp.ClientTimeout(total=timeout)

    async def invoke_method(self, actor_type: str, actor_id: str,
            method: str, data: bytes) -> bytes:
        """Invoke method defined in :class:`Actor` remotely.

        :param actor_type: str to represent Actor type.
        :param actor_id: str to represent id of Actor type.
        :param method: str to invoke method defined in :class:`Actor`.
        :param data: bytes, passed to method defined in Actor.
        :rtype: bytes
        """
        url = f'{self._get_base_url(actor_type, actor_id)}/method/{method}'
        return await self._send_bytes(method='POST', url=url, data=data)

    def _get_base_url(self, actor_type: str, actor_id: str) -> str:
        return 'http://localhost:{}/{}/actors/{}/{}'.format(
            settings.DAPR_HTTP_PORT,
            settings.DAPR_API_VERSION,
            actor_type,
            actor_id)

    async def _send_bytes(self, method: str, url: str, data: bytes, headers: dict={}) -> bytes:
        if not headers.get('content-type'):
            headers['content-type'] = _DEFAULT_CONTENT_TYPE

        r = None
        async with aiohttp.ClientSession(timeout=self._timeout) as session:
            r = await session.request(method=method, url=url, data=data, headers=headers)

        if r.status >= 200 and r.status < 300:
            return await r.read()

        r.raise_for_status()
