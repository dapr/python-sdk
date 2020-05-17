# -*- coding: utf-8 -*-

"""
Copyright (c) Microsoft Corporation.
Licensed under the MIT License.
"""

from typing import List

from dapr.actor.runtime.type_utils import is_dapr_actor, get_actor_interfaces
from dapr.actor.runtime.remindable import Remindable


class ActorTypeInformation:
    """The object that contains information about the object
    implementing an actor.
    """

    def __init__(self, name: str, implementation_class: type,
                 actor_bases: List['ActorInterface']):
        self._name = name
        self._impl_type = implementation_class
        self._actor_bases = actor_bases

    @property
    def type_name(self) -> str:
        """Returns Actor type name."""
        return self._name

    @property
    def implementation_type(self) -> type:
        """Returns Actor implementation type."""
        return self._impl_type

    @property
    def actor_interfaces(self) -> List['ActorInterface']:
        """Returns the list of :class:`ActorInterface` of this type."""
        return self._actor_bases

    def is_remindable(self) -> bool:
        """Returns True if this actor implements :class:`Remindable`."""
        return Remindable in self._impl_type.__bases__

    @classmethod
    def create(cls, actor_class: type) -> 'ActorTypeInformation':
        """Creates :class:`ActorTypeInformation` for actor_class.

        Args:
            actor_class (type): The actor implementation inherited from Actor.

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
