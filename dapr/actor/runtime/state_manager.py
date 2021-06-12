# -*- coding: utf-8 -*-

"""
Copyright (c) Microsoft Corporation and Dapr Contributors.
Licensed under the MIT License.
"""

import asyncio

from dapr.actor.runtime.state_change import StateChangeKind, ActorStateChange

from typing import Callable, Dict, Generic, List, Tuple, TypeVar, Optional, TYPE_CHECKING
if TYPE_CHECKING:
    from dapr.actor.runtime.actor import Actor

T = TypeVar('T')


class StateMetadata(Generic[T]):
    def __init__(self, value: T, change_kind: StateChangeKind):
        self._value = value
        self._change_kind = change_kind

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


class ActorStateManager(Generic[T]):
    def __init__(self, actor: 'Actor'):
        self._actor = actor
        if not actor.runtime_ctx:
            raise AttributeError('runtime context was not set')
        self._type_name = actor.runtime_ctx.actor_type_info.type_name

        self._state_change_tracker: Dict[str, StateMetadata] = {}

    async def add_state(self, state_name: str, value: T) -> None:
        if not await self.try_add_state(state_name, value):
            raise ValueError(f'The actor state name {state_name} already exist.')

    async def try_add_state(self, state_name: str, value: T) -> bool:
        if state_name in self._state_change_tracker:
            state_metadata = self._state_change_tracker[state_name]
            if state_metadata.change_kind == StateChangeKind.remove:
                self._state_change_tracker[state_name] = \
                    StateMetadata(value, StateChangeKind.update)
                return True
            return False

        existed = await self._actor.runtime_ctx.state_provider.contains_state(
            self._type_name, self._actor.id.id, state_name)
        if not existed:
            return False

        self._state_change_tracker[state_name] = StateMetadata(value, StateChangeKind.add)
        return True

    async def get_state(self, state_name: str) -> Optional[T]:
        has_value, val = await self.try_get_state(state_name)
        if has_value:
            return val
        else:
            raise KeyError(f'Actor State with name {state_name} was not found.')

    async def try_get_state(self, state_name: str) -> Tuple[bool, Optional[T]]:
        if state_name in self._state_change_tracker:
            state_metadata = self._state_change_tracker[state_name]
            if state_metadata.change_kind == StateChangeKind.remove:
                return False, None
            return True, state_metadata.value
        has_value, val = await self._actor.runtime_ctx.state_provider.try_load_state(
            self._type_name, self._actor.id.id, state_name)
        if has_value:
            self._state_change_tracker[state_name] = StateMetadata(val, StateChangeKind.none)
        return has_value, val

    async def set_state(self, state_name: str, value: T) -> None:
        if state_name in self._state_change_tracker:
            state_metadata = self._state_change_tracker[state_name]
            state_metadata.value = value

            if state_metadata.change_kind == StateChangeKind.none \
                    or state_metadata.change_kind == StateChangeKind.remove:
                state_metadata.change_kind = StateChangeKind.update
            self._state_change_tracker[state_name] = state_metadata
            return

        existed = await self._actor.runtime_ctx.state_provider.contains_state(
            self._type_name, self._actor.id.id, state_name)
        if existed:
            self._state_change_tracker[state_name] = StateMetadata(value, StateChangeKind.update)
        else:
            self._state_change_tracker[state_name] = StateMetadata(value, StateChangeKind.add)

    async def remove_state(self, state_name: str) -> None:
        if not await self.try_remove_state(state_name):
            raise KeyError(f'Actor State with name {state_name} was not found.')

    async def try_remove_state(self, state_name: str) -> bool:
        if state_name in self._state_change_tracker:
            state_metadata = self._state_change_tracker[state_name]
            if state_metadata.change_kind == StateChangeKind.remove:
                return False
            elif state_metadata.change_kind == StateChangeKind.add:
                self._state_change_tracker.pop(state_name, None)
                return True
            state_metadata.change_kind = StateChangeKind.remove
            return True

        existed = await self._actor.runtime_ctx.state_provider.contains_state(
            self._type_name, self._actor.id.id, state_name)
        if existed:
            self._state_change_tracker[state_name] = StateMetadata(None, StateChangeKind.remove)
            return True
        return False

    async def contains_state(self, state_name: str) -> bool:
        if state_name in self._state_change_tracker:
            state_metadata = self._state_change_tracker[state_name]
            return state_metadata.change_kind != StateChangeKind.remove
        return await self._actor.runtime_ctx.state_provider.contains_state(
            self._type_name, self._actor.id.id, state_name)

    async def get_or_add_state(self, state_name: str, value: T) -> Optional[T]:
        has_value, val = await self.try_get_state(state_name)
        if has_value:
            return val
        change_kind = StateChangeKind.update if self.is_state_marked_for_remove(state_name) \
            else StateChangeKind.add
        self._state_change_tracker[state_name] = StateMetadata(value, change_kind)
        return value

    async def add_or_update_state(
            self, state_name: str,
            value: T, update_value_factory: Callable[[str, T], T]) -> T:
        if not callable(update_value_factory):
            raise AttributeError('update_value_factory is not callable')

        if state_name in self._state_change_tracker:
            state_metadata = self._state_change_tracker[state_name]
            if state_metadata.change_kind == StateChangeKind.remove:
                self._state_change_tracker[state_name] = \
                    StateMetadata(value, StateChangeKind.update)
                return value
            new_value = update_value_factory(state_name, state_metadata.value)
            state_metadata.value = new_value
            if state_metadata.change_kind == StateChangeKind.none:
                state_metadata.change_kind = StateChangeKind.update
            self._state_change_tracker[state_name] = state_metadata
            return new_value

        has_value, val = await self._actor.runtime_ctx.state_provider.try_load_state(
            self._type_name, self._actor.id.id, state_name)

        if has_value:
            new_value = update_value_factory(state_name, val)
            self._state_change_tracker[state_name] = \
                StateMetadata(new_value, StateChangeKind.update)
            return new_value
        self._state_change_tracker[state_name] = \
            StateMetadata(value, StateChangeKind.add)
        return value

    async def get_state_names(self) -> List[str]:
        # TODO: Get all state names from Dapr once implemented.
        def append_names_sync():
            state_names = []
            for key, value in self._state_change_tracker.items():
                if value.change_kind == StateChangeKind.add:
                    state_names.append(key)
                elif value.change_kind == StateChangeKind.remove:
                    state_names.append(key)
            return state_names

        default_loop = asyncio.get_running_loop()
        return await default_loop.run_in_executor(None, append_names_sync)

    async def clear_cache(self) -> None:
        default_loop = asyncio.get_running_loop()
        await default_loop.run_in_executor(None, self._state_change_tracker.clear)

    async def save_state(self) -> None:
        if len(self._state_change_tracker) == 0:
            return

        state_changes = []
        states_to_remove = []
        for state_name, state_metadata in self._state_change_tracker.items():
            if state_metadata.change_kind == StateChangeKind.none:
                continue
            state_changes.append(ActorStateChange(
                state_name, state_metadata.value,
                state_metadata.change_kind))
            if state_metadata.change_kind == StateChangeKind.remove:
                states_to_remove.append(state_name)
            # Mark the states as unmodified so that tracking for next invocation is done correctly.
            state_metadata.change_kind = StateChangeKind.none
        if len(state_changes) > 0:
            await self._actor.runtime_ctx.state_provider.save_state(
                self._type_name, self._actor.id.id, state_changes)
        for state_name in states_to_remove:
            self._state_change_tracker.pop(state_name, None)

    def is_state_marked_for_remove(self, state_name: str) -> bool:
        return state_name in self._state_change_tracker and \
            self._state_change_tracker[state_name].change_kind == StateChangeKind.remove
