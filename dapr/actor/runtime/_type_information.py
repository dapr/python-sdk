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

from dapr.actor.runtime.remindable import Remindable
from dapr.actor.runtime._type_utils import is_dapr_actor, get_actor_interfaces

from typing import List, Type, TYPE_CHECKING
if TYPE_CHECKING:
    from dapr.actor.actor_interface import ActorInterface  # noqa: F401
    from dapr.actor.runtime.actor import Actor  # noqa: F401


class ActorTypeInformation:
    """The object that contains information about the object
    implementing an actor.
    """

    def __init__(self, name: str, implementation_class: Type['Actor'],
                 actor_bases: List[Type['ActorInterface']]):
        self._name = name
        self._impl_type = implementation_class
        self._actor_bases = actor_bases

    @property
    def type_name(self) -> str:
        """Returns Actor type name."""
        return self._name

    @property
    def implementation_type(self) -> Type['Actor']:
        """Returns Actor implementation type."""
        return self._impl_type

    @property
    def actor_interfaces(self) -> List[Type['ActorInterface']]:
        """Returns the list of :class:`ActorInterface` of this type."""
        return self._actor_bases

    def is_remindable(self) -> bool:
        """Returns True if this actor implements :class:`Remindable`."""
        return Remindable in self._impl_type.__bases__

    @classmethod
    def create(cls, actor_class: Type['Actor']) -> 'ActorTypeInformation':
        """Creates :class:`ActorTypeInformation` for actor_class.

        Args:
            actor_class (:class:`Actor`): The actor implementation inherited from Actor.

        Returns:
            :class:`ActorTypeInformation`: includes type name, actor_class type,
                  and actor base class deriving :class:`ActorInterface`
        """
        if not is_dapr_actor(actor_class):
            raise ValueError(f'{actor_class.__name__} is not actor')

        actors = get_actor_interfaces(actor_class)
        if len(actors) == 0:
            raise ValueError(f'{actor_class.__name__} does not implement ActorInterface')

        return ActorTypeInformation(actor_class.__name__, actor_class, actors)
