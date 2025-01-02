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

import asyncio
from contextvars import ContextVar
from typing import TYPE_CHECKING, Any, Callable, Dict, List, Optional, Tuple, TypeVar

from dapr.actor.runtime._reminder_data import ActorReminderData
from dapr.actor.runtime._timer_data import ActorTimerData
from dapr.actor.runtime.state_change import ActorStateChange, StateChangeKind
from dapr.actor.runtime.state_manager import ActorStateManager, StateMetadata

if TYPE_CHECKING:
    from dapr.actor.runtime.mock_actor import MockActor

T = TypeVar('T')
CONTEXT: ContextVar[Optional[Dict[str, Any]]] = ContextVar('state_tracker_context')


class MockStateManager(ActorStateManager):
    def __init__(self, actor: 'MockActor', initstate: Optional[dict]):
        self._actor = actor
        self._default_state_change_tracker: Dict[str, StateMetadata] = {}
        self._mock_state: Dict[str, Any] = {}
        self._mock_timers: Dict[str, ActorTimerData] = {}
        self._mock_reminders: Dict[str, ActorReminderData] = {}
        if initstate:
            self._mock_state = initstate

    async def add_state(self, state_name: str, value: T) -> None:
        if not await self.try_add_state(state_name, value):
            raise ValueError(f'The actor state name {state_name} already exist.')

    async def try_add_state(self, state_name: str, value: T) -> bool:
        if state_name in self._default_state_change_tracker:
            state_metadata = self._default_state_change_tracker[state_name]
            if state_metadata.change_kind == StateChangeKind.remove:
                self._default_state_change_tracker[state_name] = StateMetadata(
                    value, StateChangeKind.update
                )
                return True
            return False
        existed = state_name in self._mock_state
        if existed:
            return False
        self._default_state_change_tracker[state_name] = StateMetadata(value, StateChangeKind.add)
        self._mock_state[state_name] = value
        return True

    async def get_state(self, state_name: str) -> Optional[T]:
        has_value, val = await self.try_get_state(state_name)
        if has_value:
            return val
        else:
            raise KeyError(f'Actor State with name {state_name} was not found.')

    async def try_get_state(self, state_name: str) -> Tuple[bool, Optional[T]]:
        if state_name in self._default_state_change_tracker:
            state_metadata = self._default_state_change_tracker[state_name]
            if state_metadata.change_kind == StateChangeKind.remove:
                return False, None
            return True, state_metadata.value
        has_value = state_name in self._mock_state
        val = self._mock_state.get(state_name)
        if has_value:
            self._default_state_change_tracker[state_name] = StateMetadata(
                val, StateChangeKind.none
            )
        return has_value, val

    async def set_state(self, state_name: str, value: T) -> None:
        await self.set_state_ttl(state_name, value, None)

    async def set_state_ttl(self, state_name: str, value: T, ttl_in_seconds: Optional[int]) -> None:
        if ttl_in_seconds is not None and ttl_in_seconds < 0:
            return

        if state_name in self._default_state_change_tracker:
            state_metadata = self._default_state_change_tracker[state_name]
            state_metadata.value = value
            state_metadata.ttl_in_seconds = ttl_in_seconds

            if (
                state_metadata.change_kind == StateChangeKind.none
                or state_metadata.change_kind == StateChangeKind.remove
            ):
                state_metadata.change_kind = StateChangeKind.update
            self._default_state_change_tracker[state_name] = state_metadata
            self._mock_state[state_name] = value
            return

        existed = state_name in self._mock_state
        if existed:
            self._default_state_change_tracker[state_name] = StateMetadata(
                value, StateChangeKind.update, ttl_in_seconds
            )
        else:
            self._default_state_change_tracker[state_name] = StateMetadata(
                value, StateChangeKind.add, ttl_in_seconds
            )
        self._mock_state[state_name] = value

    async def remove_state(self, state_name: str) -> None:
        if not await self.try_remove_state(state_name):
            raise KeyError(f'Actor State with name {state_name} was not found.')

    async def try_remove_state(self, state_name: str) -> bool:
        if state_name in self._default_state_change_tracker:
            state_metadata = self._default_state_change_tracker[state_name]
            if state_metadata.change_kind == StateChangeKind.remove:
                return False
            elif state_metadata.change_kind == StateChangeKind.add:
                self._default_state_change_tracker.pop(state_name, None)
                self._mock_state.pop(state_name, None)
                return True
            self._mock_state.pop(state_name, None)
            state_metadata.change_kind = StateChangeKind.remove
            return True

        existed = state_name in self._mock_state
        if existed:
            self._default_state_change_tracker[state_name] = StateMetadata(
                None, StateChangeKind.remove
            )
            self._mock_state.pop(state_name, None)
            return True
        return False

    async def contains_state(self, state_name: str) -> bool:
        if state_name in self._default_state_change_tracker:
            state_metadata = self._default_state_change_tracker[state_name]
            return state_metadata.change_kind != StateChangeKind.remove
        return state_name in self._mock_state

    async def get_or_add_state(self, state_name: str, value: T) -> Optional[T]:
        has_value, val = await self.try_get_state(state_name)
        if has_value:
            return val
        change_kind = (
            StateChangeKind.update
            if self.is_state_marked_for_remove(state_name)
            else StateChangeKind.add
        )
        self._mock_state[state_name] = value
        self._default_state_change_tracker[state_name] = StateMetadata(value, change_kind)
        return value

    async def add_or_update_state(
        self, state_name: str, value: T, update_value_factory: Callable[[str, T], T]
    ) -> T:
        if not callable(update_value_factory):
            raise AttributeError('update_value_factory is not callable')

        if state_name in self._default_state_change_tracker:
            state_metadata = self._default_state_change_tracker[state_name]
            if state_metadata.change_kind == StateChangeKind.remove:
                self._default_state_change_tracker[state_name] = StateMetadata(
                    value, StateChangeKind.update
                )
                self._mock_state[state_name] = value
                return value
            new_value = update_value_factory(state_name, state_metadata.value)
            state_metadata.value = new_value
            if state_metadata.change_kind == StateChangeKind.none:
                state_metadata.change_kind = StateChangeKind.update
            self._default_state_change_tracker[state_name] = state_metadata
            self._mock_state[state_name] = new_value
            return new_value

        has_value = state_name in self._mock_state
        val: Any = self._mock_state.get(state_name)
        if has_value:
            new_value = update_value_factory(state_name, val)
            self._default_state_change_tracker[state_name] = StateMetadata(
                new_value, StateChangeKind.update
            )
            self._mock_state[state_name] = new_value
            return new_value
        self._default_state_change_tracker[state_name] = StateMetadata(value, StateChangeKind.add)
        self._mock_state[state_name] = value
        return value

    async def get_state_names(self) -> List[str]:
        # TODO: Get all state names from Dapr once implemented.
        def append_names_sync():
            state_names = []
            for key, value in self._default_state_change_tracker.items():
                if value.change_kind == StateChangeKind.add:
                    state_names.append(key)
                elif value.change_kind == StateChangeKind.remove:
                    state_names.append(key)
            return state_names

        default_loop = asyncio.get_running_loop()
        return await default_loop.run_in_executor(None, append_names_sync)

    async def clear_cache(self) -> None:
        self._default_state_change_tracker.clear()

    async def save_state(self) -> None:
        if len(self._default_state_change_tracker) == 0:
            return

        state_changes = []
        states_to_remove = []
        for state_name, state_metadata in self._default_state_change_tracker.items():
            if state_metadata.change_kind == StateChangeKind.none:
                continue
            state_changes.append(
                ActorStateChange(
                    state_name,
                    state_metadata.value,
                    state_metadata.change_kind,
                    state_metadata.ttl_in_seconds,
                )
            )
            if state_metadata.change_kind == StateChangeKind.remove:
                states_to_remove.append(state_name)
            # Mark the states as unmodified so that tracking for next invocation is done correctly.
            state_metadata.change_kind = StateChangeKind.none
        for state_name in states_to_remove:
            self._default_state_change_tracker.pop(state_name, None)

    def is_state_marked_for_remove(self, state_name: str) -> bool:
        return (
            state_name in self._default_state_change_tracker
            and self._default_state_change_tracker[state_name].change_kind == StateChangeKind.remove
        )
