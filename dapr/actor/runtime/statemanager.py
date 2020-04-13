# -*- coding: utf-8 -*-

"""
Copyright (c) Microsoft Corporation.
Licensed under the MIT License.
"""

from enum import Enum
from typing import TypeVar, Generic, List, Any, Tuple, Callable

from dapr.actor.runtime.actor import Actor

T = TypeVar('T')

class StateChangeKind(Enum):
    """A enumeration that represents the kind of state change for an actor state
    when saves change is called to a set of actor states.
    """
    # No change in state
    none = 0
    # The state needs to be added
    add = 1
    # The state needs to be updated
    update = 2
    # The state needs to be removed
    remove = 3


class ActorStateChange(Generic[T]):
    def __init__(self, state_name: str, value: T, change_kind: StateChangeKind):
        self._state_name = state_name
        self._value = value
        self._change_kind = change_kind

    @property
    def state_name(self) -> str:
        return self._state_name
    
    @property
    def value(self) -> T:
        return self._value

    @property
    def change_kind(self) -> StateChangeKind:
        return self._change_kind


class StateMetadata(Generic[T]):
    def __init__(self, value: T, change_kind):
        self._value = value
        self._change_kind = change_kind
    
    @property
    def value(self) -> T:
        return self._value
    
    @property
    def change_kind(self):
        return self._change_kind

class ActorStateManager(Generic[T]):
    def __init__(self, actor: Actor):
        self._actor = actor
        self._type_name = actor.runtime_ctx.actor_type_info.type_name
        self._state_change_tracker = {}

    async def add_state(self, state_name: str, value: T) -> None:
        if not await self.try_add_state(state_name, value):
            raise NotImplementedError(f'The actor state name {state_name} already exist.')

    async def try_add_state(self, state_name: str, value: T) -> bool:
        if state_name in self._state_change_tracker:
            state_metadata = self._state_change_tracker[state_name]
            if state_metadata.change_kind == StateChangeKind.remove:
                self._state_change_tracker[state_name] = StateMetadata(value, StateChangeKind.update)
                return True
            return False
        
        # TODO: await this.actor.ActorService.StateProvider.ContainsStateAsync(this.actorTypeName, this.actor.Id.ToString(), stateName, cancellationToken) -> return false
        if False:
            return False

        self._state_change_tracker[state_name] = StateMetadata(value, StateChangeKind.add)
        return True

    async def get_state(self, state_name: str) -> T:
        has_value, val = self.try_get_state(state_name)
        if has_value: return val
        raise KeyError(f'Actor State with name {state_name} was not found.')
        
    async def try_get_state(self, state_name: str) -> Tuple[bool, T]:
        if state_name in self._state_change_tracker:
            state_metadata = self._state_change_tracker[state_name]
            if state_metadata.change_kind == StateChangeKind.remove:
                return False, None
            return True, state_metadata.value
        
        # this.actor.ActorService.StateProvider.TryLoadStateAsync<T>(this.actorTypeName, this.actor.Id.ToString(), stateName, cancellationToken)
        has_value, val = (True, 'test')
        if has_value:
            self._state_change_tracker[state_name] = StateMetadata(val, StateChangeKind.none)
        return has_value, val

    async def set_state(self, state_name: str, value: T) -> None:
        if state_name in self._state_change_tracker:
            state_metadata = self._state_change_tracker[state_name]
            state_metadata.value = value

            if state_metadata.change_kind == StateChangeKind.none or state_metadata.change_kind == StateChangeKind.remove:
                state_metadata.change_kind = StateChangeKind.update
        
        # await this.actor.ActorService.StateProvider.ContainsStateAsync(this.actorTypeName, this.actor.Id.ToString(), stateName, cancellationToken)
        if False:
            self._state_change_tracker[state_name] = StateMetadata(value, StateChangeKind.update)
    
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
        # await this.actor.ActorService.StateProvider.ContainsStateAsync(this.actorTypeName, this.actor.Id.ToString(), stateName, cancellationToken)
        if False:
            self._state_change_tracker[state_name] = StateMetadata(None, StateChangeKind.remove)
            return True
        return False

    async def contains_state(self, state_name: str) -> bool:
        if state_name in self._state_change_tracker:
            state_metadata = self._state_change_tracker[state_name]
            return state_metadata.change_kind != StateChangeKind.remove
        
        # await this.actor.ActorService.StateProvider.ContainsStateAsync(this.actorTypeName, this.actor.Id.ToString(), stateName, cancellationToken)
        contained = True
        return contained

    async def get_or_add_state(self, state_name: str, value: T) -> T:
        has_value, val = self.try_get_state(state_name)
        if has_value: return val
        change_kind = StateChangeKind.update if self.is_state_marked_for_remove(state_name) else StateChangeKind.add
        self._state_change_tracker[state_name] = StateMetadata(value, change_kind)
        return value

    async def add_or_update_state(self, state_name: str, value: T, update_value_factory: Callable[[str, T], T]) -> T:
        if state_name in self._state_change_tracker:
            state_metadata = self._state_change_tracker[state_name]
            if state_metadata.change_kind == StateChangeKind.remove:
                self._state_change_tracker[state_name] = StateMetadata(value, StateChangeKind.update)
                return value
            
            new_value = update_value_factory(state_name, state_metadata.value)
            state_metadata.value = new_value
            if state_metadata.change_kind == StateChangeKind.none:
                state_metadata.change_kind = StateChangeKind.update
            return new_value
        
        # this.actor.ActorService.StateProvider.TryLoadStateAsync<T>(this.actorTypeName, this.actor.Id.ToString(), stateName, cancellationToken);
        has_value, val = (True, None)
        if has_value:
            new_value = update_value_factory(state_name, val)
            self._state_change_tracker[state_name] = StateMetadata(new_value, StateChangeKind.update)
            return new_value
        
        self._state_change_tracker[state_name] = StateMetadata(value, StateChangeKind.add)
        return value

    async def get_state_names(self) -> List[str]:
        # TODO: Get all state names from Dapr once implemented.
        # var namesFromStateProvider = await this.stateProvider.EnumerateStateNamesAsync(this.actor.Id, cancellationToken);

        state_names = []

        for key, value in self._state_change_tracker.items():
            if value.change_kind == StateChangeKind.add:
                state_names.append(key)
            elif value.change_kind == StateChangeKind.remove:
                state_names.append(key)

        return state_names

    def clear_cache(self) -> None:
        self._state_change_tracker.clear()

    def save_state(self) -> None:
        if len(self._state_change_tracker) == 0:
            return
        state_changes = []
        states_to_remove = []
        for state_name, state_metadata in self._state_change_tracker.items():
            if state_metadata.change_kind == StateChangeKind.none:
                continue

            state_changes.append(ActorStateChange(state_name, state_metadata.value, state_metadata.change_kind))
            if state_metadata.change_kind == StateChangeKind.remove:
                states_to_remove.append(state_name)

            # Mark the states as unmodified so that tracking for next invocation is done correctly.
            state_metadata.change_kind = StateChangeKind.none
        
        if len(state_changes) > 0:
            pass
            # await this.actor.ActorService.StateProvider.SaveStateAsync(this.actorTypeName, this.actor.Id.ToString(), stateChangeList.AsReadOnly(), cancellationToken);
        
        for state_name in states_to_remove:
            self._state_change_tracker.pop(state_name, None)


    def is_state_marked_for_remove(self, state_name: str) -> bool:
        return state_name in self._state_change_tracker and self._state_change_tracker[state_name].change_kind == StateChangeKind.remove
