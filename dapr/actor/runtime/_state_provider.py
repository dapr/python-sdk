# -*- coding: utf-8 -*-

"""
Copyright 2021 The Dapr Authors
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

import io

from typing import Any, List, Type, Tuple
from dapr.actor.runtime.state_change import StateChangeKind, ActorStateChange
from dapr.clients.base import DaprActorClientBase
from dapr.serializers import Serializer, DefaultJSONSerializer


# Mapping StateChangeKind to Dapr State Operation
_MAP_CHANGE_KIND_TO_OPERATION = {
    StateChangeKind.remove: b'delete',
    StateChangeKind.add: b'upsert',
    StateChangeKind.update: b'upsert',
}


class StateProvider:
    """The adapter class for StateManager to use Dapr Actor Client.

    This provides the decorator methods to load and save states and check the existence of states.
    """
    def __init__(
            self,
            actor_client: DaprActorClientBase,
            state_serializer: Serializer = DefaultJSONSerializer()):
        self._state_client = actor_client
        self._state_serializer = state_serializer

    async def try_load_state(
            self, actor_type: str, actor_id: str,
            state_name: str, state_type: Type[Any] = object) -> Tuple[bool, Any]:
        raw_state_value = await self._state_client.get_state(actor_type, actor_id, state_name)
        if (not raw_state_value) or len(raw_state_value) == 0:
            return (False, None)
        result = self._state_serializer.deserialize(raw_state_value, state_type)
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

        json_output = io.BytesIO()
        json_output.write(b'[')
        first_state = True
        for state in state_changes:
            if not first_state:
                json_output.write(b',')
            operation = _MAP_CHANGE_KIND_TO_OPERATION.get(state.change_kind) or b''
            json_output.write(b'{"operation":"')
            json_output.write(operation)
            json_output.write(b'","request":{"key":"')
            json_output.write(state.state_name.encode('utf-8'))
            json_output.write(b'"')
            if state.value is not None:
                serialized = self._state_serializer.serialize(state.value)
                json_output.write(b',"value":')
                json_output.write(serialized)
            json_output.write(b'}}')
            first_state = False
        json_output.write(b']')
        data = json_output.getvalue()
        json_output.close()
        await self._state_client.save_state_transactionally(actor_type, actor_id, data)
