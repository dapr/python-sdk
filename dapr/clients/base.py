# -*- coding: utf-8 -*-

"""
Copyright (c) Microsoft Corporation and Dapr Contributors.
Licensed under the MIT License.
"""

from abc import ABC, abstractmethod
from typing import Optional


DEFAULT_ENCODING = 'utf-8'
DEFAULT_JSON_CONTENT_TYPE = f'application/json; charset={DEFAULT_ENCODING}'


class DaprActorClientBase(ABC):
    """A base class that represents Dapr Actor Client.
    """

    @abstractmethod
    async def invoke_method(
            self, actor_type: str, actor_id: str,
            method: str, data: Optional[bytes] = None) -> bytes:
        ...

    @abstractmethod
    async def save_state_transactionally(
            self, actor_type: str, actor_id: str,
            data: bytes) -> None:
        ...

    @abstractmethod
    async def get_state(
            self, actor_type: str, actor_id: str, name: str) -> bytes:
        ...

    @abstractmethod
    async def register_reminder(
            self, actor_type: str, actor_id: str, name: str, data: bytes) -> None:
        ...

    @abstractmethod
    async def unregister_reminder(
            self, actor_type: str, actor_id: str, name: str) -> None:
        ...

    @abstractmethod
    async def register_timer(
            self, actor_type: str, actor_id: str, name: str, data: bytes) -> None:
        ...

    @abstractmethod
    async def unregister_timer(
            self, actor_type: str, actor_id: str, name: str) -> None:
        ...
