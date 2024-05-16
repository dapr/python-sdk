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

from enum import Enum
from typing import TypeVar, Generic, Optional

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
    def __init__(
        self,
        state_name: str,
        value: T,
        change_kind: StateChangeKind,
        ttl_in_seconds: Optional[int] = None,
    ):
        self._state_name = state_name
        self._value = value
        self._change_kind = change_kind
        self._ttl_in_seconds = ttl_in_seconds

    @property
    def state_name(self) -> str:
        return self._state_name

    @property
    def value(self) -> T:
        return self._value

    @property
    def change_kind(self) -> StateChangeKind:
        return self._change_kind

    @property
    def ttl_in_seconds(self) -> Optional[int]:
        return self._ttl_in_seconds
