# -*- coding: utf-8 -*-

"""
Copyright (c) Microsoft Corporation.
Licensed under the MIT License.
"""

from dapr.actor.runtime.typeutils import is_dapr_actor, get_actor_interfaces

class ActorTypeInformation:
    """The object that contains information about the object
    implementing an actor.
    """

    def __init__(self, name: str, implementation_class: type,
                 actor_bases: list):
        self._name = name
        self._impl_type = implementation_class
        self._actor_bases = actor_bases

    @property
    def type_name(self) -> str:
        """Return Actor type name"""
        return self._name

    @property
    def implementation_type(self) -> type:
        """Return Actor implementation type"""
        return self._impl_type

    @property
    def actor_interfaces(self) -> list:
        """Return the list of :class:`ActorInterface` implemented
        by :class:`Actor`.
        """
        return self._actor_bases

    @classmethod
    def create(cls, actor_class: type) -> 'ActorTypeInformation':
        """Creates :class:`ActorTypeInformation` for actor_class.

        :param type actor_class: The actor implementation inherited from Actor
        :returns: ActorTypeInformation that includes type name, actor_class type,
                  and actor base class deriving :class:`ActorInterface`
        :rtype: ActorTypeInformation
        """
        if not is_dapr_actor(actor_class):
            raise ValueError(f'{actor_class.__name__} is not actor')

        actors = get_actor_interfaces(actor_class)
        if len(actors) == 0:
            raise ValueError(f'{actor_class.__name__} does not implement ActorInterface')

        return ActorTypeInformation(actor_class.__name__, actor_class, actors)
