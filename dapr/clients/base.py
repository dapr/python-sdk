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

from abc import ABC, abstractmethod
from typing import Optional


DEFAULT_ENCODING = 'utf-8'
DEFAULT_JSON_CONTENT_TYPE = f'application/json; charset={DEFAULT_ENCODING}'


class DaprActorClientBase(ABC):
    """A base class that represents Dapr Actor Client."""

    @abstractmethod
    async def invoke_method(
        self, actor_type: str, actor_id: str, method: str, data: Optional[bytes] = None
    ) -> bytes:
        ...

    @abstractmethod
    async def save_state_transactionally(self, actor_type: str, actor_id: str, data: bytes) -> None:
        ...

    @abstractmethod
    async def get_state(self, actor_type: str, actor_id: str, name: str) -> bytes:
        ...

    @abstractmethod
    async def register_reminder(
        self, actor_type: str, actor_id: str, name: str, data: bytes
    ) -> None:
        ...

    @abstractmethod
    async def unregister_reminder(self, actor_type: str, actor_id: str, name: str) -> None:
        ...

    @abstractmethod
    async def register_timer(self, actor_type: str, actor_id: str, name: str, data: bytes) -> None:
        ...

    @abstractmethod
    async def unregister_timer(self, actor_type: str, actor_id: str, name: str) -> None:
        ...
