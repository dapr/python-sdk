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

from typing import Callable, Dict, Optional, Union, TYPE_CHECKING

from dapr.clients.http.helpers import get_api_url

if TYPE_CHECKING:
    from dapr.serializers import Serializer

from dapr.clients.http.client import DaprHttpClient
from dapr.clients.base import DaprActorClientBase
from dapr.clients.retry import RetryPolicy

DAPR_REENTRANCY_ID_HEADER = 'Dapr-Reentrancy-Id'


class DaprActorHttpClient(DaprActorClientBase):
    """A Dapr Actor http client implementing :class:`DaprActorClientBase`"""

    def __init__(
        self,
        message_serializer: 'Serializer',
        timeout: int = 60,
        headers_callback: Optional[Callable[[], Dict[str, str]]] = None,
        retry_policy: Optional[RetryPolicy] = None,
    ):
        """Invokes Dapr Actors over HTTP.

        Args:
            message_serializer (Serializer): Dapr serializer.
            timeout (int, optional): Timeout in seconds, defaults to 60.
            headers_callback (lambda: Dict[str, str]], optional): Generates header for each request.
            retry_policy (RetryPolicy optional): Specifies retry behaviour
        """
        self._client = DaprHttpClient(message_serializer, timeout, headers_callback, retry_policy)

    async def invoke_method(
        self, actor_type: str, actor_id: str, method: str, data: Optional[bytes] = None
    ) -> bytes:
        """Invoke method defined in :class:`Actor` remotely.

        Args:
            actor_type (str): Actor type.
            actor_id (str): Id of Actor type.
            method (str): Method name defined in :class:`Actor`.
            bytes data (bytes): data which will be passed to the target actor.

        Returns:
            bytes: the response from the actor.
        """
        url = f'{self._get_base_url(actor_type, actor_id)}/method/{method}'

        # import to avoid circular dependency
        from dapr.actor.runtime.reentrancy_context import reentrancy_ctx

        reentrancy_id = reentrancy_ctx.get()
        headers: Dict[str, Union[bytes, str]] = (
            {DAPR_REENTRANCY_ID_HEADER: reentrancy_id} if reentrancy_id else {}
        )

        body, _ = await self._client.send_bytes(method='POST', url=url, data=data, headers=headers)

        return body

    async def save_state_transactionally(self, actor_type: str, actor_id: str, data: bytes) -> None:
        """Save state transactionally.

        Args:
            actor_type (str): Actor type.
            actor_id (str): Id of Actor type.
            data (bytes): Json-serialized the transactional state operations.
        """
        url = f'{self._get_base_url(actor_type, actor_id)}/state'
        await self._client.send_bytes(method='PUT', url=url, data=data)

    async def get_state(self, actor_type: str, actor_id: str, name: str) -> bytes:
        """Get state value for name key.

        Args:
            actor_type (str): Actor type.
            actor_id (str): Id of Actor type.
            name (str): The name of state.

        Returns:
            bytes: the value of the state.
        """
        url = f'{self._get_base_url(actor_type, actor_id)}/state/{name}'
        body, _ = await self._client.send_bytes(method='GET', url=url, data=None)
        return body

    async def register_reminder(
        self, actor_type: str, actor_id: str, name: str, data: bytes
    ) -> None:
        """Register actor reminder.

        Args:
            actor_type (str): Actor type.
            actor_id (str): Id of Actor type.
            name (str): The name of reminder
            data (bytes): Reminder request json body.
        """
        url = f'{self._get_base_url(actor_type, actor_id)}/reminders/{name}'
        await self._client.send_bytes(method='PUT', url=url, data=data)

    async def unregister_reminder(self, actor_type: str, actor_id: str, name: str) -> None:
        """Unregister actor reminder.

        Args:
            actor_type (str): Actor type.
            actor_id (str): Id of Actor type.
            name (str):  the name of reminder.
        """
        url = f'{self._get_base_url(actor_type, actor_id)}/reminders/{name}'
        await self._client.send_bytes(method='DELETE', url=url, data=None)

    async def register_timer(self, actor_type: str, actor_id: str, name: str, data: bytes) -> None:
        """Register actor timer.

        Args:
            actor_type (str): Actor type.
            actor_id (str): Id of Actor type.
            name (str): The name of reminder.
            data (bytes): Timer request json body.
        """
        url = f'{self._get_base_url(actor_type, actor_id)}/timers/{name}'
        await self._client.send_bytes(method='PUT', url=url, data=data)

    async def unregister_timer(self, actor_type: str, actor_id: str, name: str) -> None:
        """Unregister actor timer.

        Args:
            actor_type (str): Actor type.
            actor_id (str): Id of Actor type.
            name (str): The name of timer
        """
        url = f'{self._get_base_url(actor_type, actor_id)}/timers/{name}'
        await self._client.send_bytes(method='DELETE', url=url, data=None)

    def _get_base_url(self, actor_type: str, actor_id: str) -> str:
        return '{}/actors/{}/{}'.format(get_api_url(), actor_type, actor_id)
