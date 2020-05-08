# -*- coding: utf-8 -*-

"""
Copyright (c) Microsoft Corporation.
Licensed under the MIT License.
"""
import aiohttp

from dapr.conf import settings
from dapr.clients.base import DaprActorClientBase


CONTENT_TYPE_HEADER = 'content-type'
DEFAULT_ENCODING = 'utf-8'
DEFAULT_JSON_CONTENT_TYPE = f'application/json; charset={DEFAULT_ENCODING}'


class DaprActorHttpClient(DaprActorClientBase):
    """A Dapr Actor http client implementing :class:`DaprActorClientBase`"""

    def __init__(self, timeout=60):
        self._timeout = aiohttp.ClientTimeout(total=timeout)

    async def invoke_method(
            self, actor_type: str, actor_id: str,
            method: str, data: bytes) -> bytes:
        """Invoke method defined in :class:`Actor` remotely.

        :param str actor_type: str to represent Actor type.
        :param str actor_id: str to represent id of Actor type.
        :param str method: str to invoke method defined in :class:`Actor`.
        :param bytes data: bytes, passed to method defined in Actor.
        :returns: the response from actor
        :rtype: bytes
        """
        url = f'{self._get_base_url(actor_type, actor_id)}/method/{method}'
        return await self._send_bytes(method='POST', url=url, data=data)

    async def save_state_transactionally(
            self, actor_type: str, actor_id: str,
            data: bytes) -> None:
        """Save state transactionally.

        :param str actor_type: str to represent Actor type.
        :param str actor_id: str to represent id of Actor type.
        :param bytes data: bytes, passed to method defined in Actor.
        """
        url = f'{self._get_base_url(actor_type, actor_id)}/state'
        headers = {
            CONTENT_TYPE_HEADER: DEFAULT_JSON_CONTENT_TYPE,
        }
        return await self._send_bytes(method='PUT', url=url, data=data, headers=headers)

    async def get_state(
            self, actor_type: str, actor_id: str, name: str) -> bytes:
        """Get state.

        :param str actor_type: str to represent Actor type.
        :param str actor_id: str to represent id of Actor type.
        :param str name: str to represent the name of state.
        :returns: the response from actor
        :rtype: bytes
        """
        url = f'{self._get_base_url(actor_type, actor_id)}/state/{name}'
        headers = {
            CONTENT_TYPE_HEADER: DEFAULT_JSON_CONTENT_TYPE,
        }
        return await self._send_bytes(method='GET', url=url, data=None, headers=headers)

    async def register_reminder(
            self, actor_type: str, actor_id: str, name: str, data: bytes) -> None:
        """Register actor reminder.

        :param str actor_type: str to represent Actor type.
        :param str actor_id: str to represent id of Actor type.
        :param str name: str to represent the name of reminder
        :param bytes data: bytes which includes reminder request json body.
        """
        url = f'{self._get_base_url(actor_type, actor_id)}/reminders/{name}'
        headers = {
            CONTENT_TYPE_HEADER: DEFAULT_JSON_CONTENT_TYPE,
        }
        return await self._send_bytes(method='PUT', url=url, data=data, headers=headers)

    async def unregister_reminder(
            self, actor_type: str, actor_id: str, name: str) -> None:
        """Unregister actor reminder.

        :param str actor_type: str to represent Actor type.
        :param str actor_id: str to represent id of Actor type.
        :param str name: str to represent the name of reminder
        """
        url = f'{self._get_base_url(actor_type, actor_id)}/reminders/{name}'
        headers = {
            CONTENT_TYPE_HEADER: DEFAULT_JSON_CONTENT_TYPE,
        }
        return await self._send_bytes(method='DELETE', url=url, data=None, headers=headers)

    async def register_timer(
            self, actor_type: str, actor_id: str, name: str, data: bytes) -> None:
        """Register actor timer.

        :param str actor_type: str to represent Actor type.
        :param str actor_id: str to represent id of Actor type.
        :param str name: str to represent the name of reminder
        :param bytes data: bytes which includes timer request json body.
        """
        url = f'{self._get_base_url(actor_type, actor_id)}/timers/{name}'
        headers = {
            CONTENT_TYPE_HEADER: DEFAULT_JSON_CONTENT_TYPE,
        }
        return await self._send_bytes(method='PUT', url=url, data=data, headers=headers)

    async def unregister_timer(
            self, actor_type: str, actor_id: str, name: str) -> None:
        """Unregister actor timer.

        :param str actor_type: str to represent Actor type.
        :param str actor_id: str to represent id of Actor type.
        :param str name: str to represent the name of timer
        """
        url = f'{self._get_base_url(actor_type, actor_id)}/timers/{name}'
        headers = {
            CONTENT_TYPE_HEADER: DEFAULT_JSON_CONTENT_TYPE,
        }
        return await self._send_bytes(method='DELETE', url=url, data=None, headers=headers)

    def _get_base_url(self, actor_type: str, actor_id: str) -> str:
        return 'http://127.0.0.1:{}/{}/actors/{}/{}'.format(
            settings.DAPR_HTTP_PORT,
            settings.DAPR_API_VERSION,
            actor_type,
            actor_id)

    async def _send_bytes(
            self, method: str, url: str,
            data: bytes, headers: dict = {}) -> bytes:
        if not headers.get(CONTENT_TYPE_HEADER):
            headers[CONTENT_TYPE_HEADER] = DEFAULT_JSON_CONTENT_TYPE

        r = None
        async with aiohttp.ClientSession(timeout=self._timeout) as session:
            r = await session.request(method=method, url=url, data=data, headers=headers)

        if r.status >= 200 and r.status < 300:
            return await r.read()

        r.raise_for_status()
