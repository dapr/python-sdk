# -*- coding: utf-8 -*-

"""
Copyright (c) Microsoft Corporation and Dapr Contributors.
Licensed under the MIT License.
"""

from enum import Enum
from typing import TypeVar, Generic

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
