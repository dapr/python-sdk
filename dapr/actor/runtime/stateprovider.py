# -*- coding: utf-8 -*-

"""
Copyright (c) Microsoft Corporation.
Licensed under the MIT License.
"""

import base64

from typing import Generic, List, TypeVar, Tuple
from dapr.actor.runtime.statechange import StateChangeKind, ActorStateChange
from dapr.clients import DaprActorClientBase
from dapr.serializers import Serializer, DefaultJSONSerializer

T = TypeVar('T')

# Mapping StateChangeKind to Dapr State Operation
MAP_CHANGE_KIND_TO_OPERATION = {
    StateChangeKind.remove: "delete",
    StateChangeKind.add: "upsert",
    StateChangeKind.update: "upsert",
}

class StateProvider(Generic[T]):
    def __init__(
            self,
            actor_client: DaprActorClientBase,
            state_serializer: Serializer = None):
        self._state_client = actor_client
        self._state_serializer = state_serializer or DefaultJSONSerializer()

    async def try_load_state(
            self, actor_type: str, actor_id: str,
            state_name: str) -> Tuple[bool, T]:
        raw_state_value = await self._state_client.get_state(actor_type, actor_id, state_name)
        if (not raw_state_value) or len(raw_state_value) == 0:
            return (False, None)
        decoded = base64.decodebytes(raw_state_value)
        result = self._state_serializer.deserialize(decoded, T)
        return (True, result)

    async def contains_state(self, actor_type: str, actor_id: str, state_name: str) -> bool:
        raw_state_value = await self._state_client.get_state(actor_type, actor_id, state_name)
        return (raw_state_value is not None) and len(raw_state_value) > 0

    async def save_state(
            self, actor_type: str, actor_id: str,
            state_changes: List[ActorStateChange]) -> None:
        """
        Transactional state update request body:
        [
            {
                "operation": "upsert",
                "request": {
                    "key": "key1",
                    "value": "myData"
                }
            },
            {
                "operation": "delete",
                "request": {
                    "key": "key2"
                }
            }
        ]
        """

        operations = []
        for state in state_changes:
            operations.append({
                "operation": MAP_CHANGE_KIND_TO_OPERATION.get(state.change_kind) or '',
                "request": {
                    "key": state.state_name,
                    "value": state.value,
                }
            })
        serialized = self._state_serializer.serialize(operations)
        await self._state_client.save_state_transactionally(actor_type, actor_id, serialized)
