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

import asyncio
from contextvars import ContextVar

from dapr.actor.runtime.state_change import StateChangeKind, ActorStateChange
from dapr.actor.runtime.reentrancy_context import reentrancy_ctx

from typing import Any, Callable, Dict, Generic, List, Tuple, TypeVar, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from dapr.actor.runtime.actor import Actor

T = TypeVar('T')
CONTEXT: ContextVar[Optional[Dict[str, Any]]] = ContextVar('state_tracker_context')


class StateMetadata(Generic[T]):
    def __init__(
        self, value: T, change_kind: StateChangeKind, ttl_in_seconds: Optional[int] = None
    ):
        self._value = value
        self._change_kind = change_kind
        self._ttl_in_seconds = ttl_in_seconds

    @property
    def value(self) -> T:
        return self._value

    @value.setter
    def value(self, new_value: T) -> None:
        self._value = new_value

    @property
    def change_kind(self) -> StateChangeKind:
        return self._change_kind

    @change_kind.setter
    def change_kind(self, new_kind: StateChangeKind) -> None:
        self._change_kind = new_kind

    @property
    def ttl_in_seconds(self) -> Optional[int]:
        return self._ttl_in_seconds

    @ttl_in_seconds.setter
    def ttl_in_seconds(self, new_ttl_in_seconds: int) -> None:
        self._ttl_in_seconds = new_ttl_in_seconds


class ActorStateManager(Generic[T]):
    def __init__(self, actor: 'Actor'):
        self._actor = actor
        if not actor.runtime_ctx:
            raise AttributeError('runtime context was not set')
        self._type_name = actor.runtime_ctx.actor_type_info.type_name

        self._default_state_change_tracker: Dict[str, StateMetadata] = {}

    async def add_state(self, state_name: str, value: T) -> None:
        if not await self.try_add_state(state_name, value):
            raise ValueError(f'The actor state name {state_name} already exist.')

    async def try_add_state(self, state_name: str, value: T) -> bool:
        state_change_tracker = self._get_contextual_state_tracker()
        if state_name in state_change_tracker:
            state_metadata = state_change_tracker[state_name]
            if state_metadata.change_kind == StateChangeKind.remove:
                state_change_tracker[state_name] = StateMetadata(value, StateChangeKind.update)
                return True
            return False

        existed = await self._actor.runtime_ctx.state_provider.contains_state(
            self._type_name, self._actor.id.id, state_name
        )
        if not existed:
            return False

        state_change_tracker[state_name] = StateMetadata(value, StateChangeKind.add)
        return True

    async def get_state(self, state_name: str) -> Optional[T]:
        has_value, val = await self.try_get_state(state_name)
        if has_value:
            return val
        else:
            raise KeyError(f'Actor State with name {state_name} was not found.')

    async def try_get_state(self, state_name: str) -> Tuple[bool, Optional[T]]:
        state_change_tracker = self._get_contextual_state_tracker()
        if state_name in state_change_tracker:
            state_metadata = state_change_tracker[state_name]
            if state_metadata.change_kind == StateChangeKind.remove:
                return False, None
            return True, state_metadata.value
        has_value, val = await self._actor.runtime_ctx.state_provider.try_load_state(
            self._type_name, self._actor.id.id, state_name
        )
        if has_value:
            state_change_tracker[state_name] = StateMetadata(val, StateChangeKind.none)
        return has_value, val

    async def set_state(self, state_name: str, value: T) -> None:
        await self.set_state_ttl(state_name, value, None)

    async def set_state_ttl(self, state_name: str, value: T, ttl_in_seconds: Optional[int]) -> None:
        if ttl_in_seconds is not None and ttl_in_seconds < 0:
            return

        state_change_tracker = self._get_contextual_state_tracker()
        if state_name in state_change_tracker:
            state_metadata = state_change_tracker[state_name]
            state_metadata.value = value
            state_metadata.ttl_in_seconds = ttl_in_seconds

            if (
                state_metadata.change_kind == StateChangeKind.none
                or state_metadata.change_kind == StateChangeKind.remove
            ):
                state_metadata.change_kind = StateChangeKind.update
            state_change_tracker[state_name] = state_metadata
            return

        existed = await self._actor.runtime_ctx.state_provider.contains_state(
            self._type_name, self._actor.id.id, state_name
        )
        if existed:
            state_change_tracker[state_name] = StateMetadata(
                value, StateChangeKind.update, ttl_in_seconds
            )
        else:
            state_change_tracker[state_name] = StateMetadata(
                value, StateChangeKind.add, ttl_in_seconds
            )

    async def remove_state(self, state_name: str) -> None:
        if not await self.try_remove_state(state_name):
            raise KeyError(f'Actor State with name {state_name} was not found.')

    async def try_remove_state(self, state_name: str) -> bool:
        state_change_tracker = self._get_contextual_state_tracker()
        if state_name in state_change_tracker:
            state_metadata = state_change_tracker[state_name]
            if state_metadata.change_kind == StateChangeKind.remove:
                return False
            elif state_metadata.change_kind == StateChangeKind.add:
                state_change_tracker.pop(state_name, None)
                return True
            state_metadata.change_kind = StateChangeKind.remove
            return True

        existed = await self._actor.runtime_ctx.state_provider.contains_state(
            self._type_name, self._actor.id.id, state_name
        )
        if existed:
            state_change_tracker[state_name] = StateMetadata(None, StateChangeKind.remove)
            return True
        return False

    async def contains_state(self, state_name: str) -> bool:
        state_change_tracker = self._get_contextual_state_tracker()
        if state_name in state_change_tracker:
            state_metadata = state_change_tracker[state_name]
            return state_metadata.change_kind != StateChangeKind.remove
        return await self._actor.runtime_ctx.state_provider.contains_state(
            self._type_name, self._actor.id.id, state_name
        )

    async def get_or_add_state(self, state_name: str, value: T) -> Optional[T]:
        state_change_tracker = self._get_contextual_state_tracker()
        has_value, val = await self.try_get_state(state_name)
        if has_value:
            return val
        change_kind = (
            StateChangeKind.update
            if self.is_state_marked_for_remove(state_name)
            else StateChangeKind.add
        )
        state_change_tracker[state_name] = StateMetadata(value, change_kind)
        return value

    async def add_or_update_state(
        self, state_name: str, value: T, update_value_factory: Callable[[str, T], T]
    ) -> T:
        if not callable(update_value_factory):
            raise AttributeError('update_value_factory is not callable')

        state_change_tracker = self._get_contextual_state_tracker()
        if state_name in state_change_tracker:
            state_metadata = state_change_tracker[state_name]
            if state_metadata.change_kind == StateChangeKind.remove:
                state_change_tracker[state_name] = StateMetadata(value, StateChangeKind.update)
                return value
            new_value = update_value_factory(state_name, state_metadata.value)
            state_metadata.value = new_value
            if state_metadata.change_kind == StateChangeKind.none:
                state_metadata.change_kind = StateChangeKind.update
            state_change_tracker[state_name] = state_metadata
            return new_value

        has_value, val = await self._actor.runtime_ctx.state_provider.try_load_state(
            self._type_name, self._actor.id.id, state_name
        )

        if has_value:
            new_value = update_value_factory(state_name, val)
            state_change_tracker[state_name] = StateMetadata(new_value, StateChangeKind.update)
            return new_value
        state_change_tracker[state_name] = StateMetadata(value, StateChangeKind.add)
        return value

    async def get_state_names(self) -> List[str]:
        # TODO: Get all state names from Dapr once implemented.
        def append_names_sync():
            state_change_tracker = self._get_contextual_state_tracker()
            state_names = []
            for key, value in state_change_tracker.items():
                if value.change_kind == StateChangeKind.add:
                    state_names.append(key)
                elif value.change_kind == StateChangeKind.remove:
                    state_names.append(key)
            return state_names

        default_loop = asyncio.get_running_loop()
        return await default_loop.run_in_executor(None, append_names_sync)

    async def clear_cache(self) -> None:
        state_change_tracker = self._get_contextual_state_tracker()
        default_loop = asyncio.get_running_loop()
        await default_loop.run_in_executor(None, state_change_tracker.clear)

    async def save_state(self) -> None:
        state_change_tracker = self._get_contextual_state_tracker()
        if len(state_change_tracker) == 0:
            return

        state_changes = []
        states_to_remove = []
        for state_name, state_metadata in state_change_tracker.items():
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
        if len(state_changes) > 0:
            await self._actor.runtime_ctx.state_provider.save_state(
                self._type_name, self._actor.id.id, state_changes
            )
        for state_name in states_to_remove:
            state_change_tracker.pop(state_name, None)

    def is_state_marked_for_remove(self, state_name: str) -> bool:
        state_change_tracker = self._get_contextual_state_tracker()
        return (
            state_name in state_change_tracker
            and state_change_tracker[state_name].change_kind == StateChangeKind.remove
        )

    def _get_contextual_state_tracker(self) -> Dict[str, StateMetadata]:
        context = CONTEXT.get(None)
        if context is not None and reentrancy_ctx.get(None) is not None:
            return context['tracker']
        else:
            return self._default_state_change_tracker

    def set_state_context(self, contextID: Optional[str]):
        if contextID is not None:
            CONTEXT.set({'id': contextID, 'tracker': {}})
        else:
            CONTEXT.set(None)
        return
