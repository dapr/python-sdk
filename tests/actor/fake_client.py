# -*- coding: utf-8 -*-

"""
Copyright (c) Microsoft Corporation.
Licensed under the MIT License.
"""

from dapr.clients import DaprActorClientBase
from typing import Optional


# Fake Dapr Actor Client Base Class for testing
class FakeDaprActorClientBase(DaprActorClientBase):
    async def invoke_method(
            self, actor_type: str, actor_id: str,
            method: str, data: Optional[bytes] = None) -> bytes:
        ...

    async def save_state_transactionally(
            self, actor_type: str, actor_id: str,
            data: bytes) -> None:
        ...

    async def get_state(
            self, actor_type: str, actor_id: str, name: str) -> bytes:
        ...

    async def register_reminder(
            self, actor_type: str, actor_id: str, name: str, data: bytes) -> None:
        ...

    async def unregister_reminder(
            self, actor_type: str, actor_id: str, name: str) -> None:
        ...

    async def register_timer(
            self, actor_type: str, actor_id: str, name: str, data: bytes) -> None:
        ...

    async def unregister_timer(
            self, actor_type: str, actor_id: str, name: str) -> None:
        ...


class FakeDaprActorClient(FakeDaprActorClientBase):
    async def invoke_method(
            self, actor_type: str, actor_id: str,
            method: str, data: Optional[bytes] = None) -> bytes:
        return b'"expected_response"'

    async def save_state_transactionally(
            self, actor_type: str, actor_id: str,
            data: bytes) -> None:
        pass

    async def get_state(
            self, actor_type: str, actor_id: str, name: str) -> bytes:
        return b'"expected_response"'

    async def register_reminder(
            self, actor_type: str, actor_id: str,
            name: str, data: bytes) -> None:
        pass

    async def unregister_reminder(
            self, actor_type: str, actor_id: str, name: str) -> None:
        pass

    async def register_timer(
            self, actor_type: str, actor_id: str, name: str, data: bytes) -> None:
        pass

    async def unregister_timer(
            self, actor_type: str, actor_id: str, name: str) -> None:
        pass
