# -*- coding: utf-8 -*-

"""
Copyright (c) Microsoft Corporation.
Licensed under the MIT License.
"""

from dapr.actor.actor_interface import ActorInterface
from dapr.actor.runtime.actor import Actor

def is_dapr_actor(cls: object) -> bool:
    """Check if class inherits :class:`Actor`.

    :param object cls: The Actor implementation
    :returns: True if cls inherits :class:`Actor`. Otherwise, False
    :rtype: bool
    """
    return issubclass(cls, Actor)

def get_non_actor_parent_type(cls: object) -> object:
    """Get non-actor parent type by traversing parent type node

    :param object cls: The actor object
    :returns: The non actor parent object
    :rtype: object
    """
    bases = cls.__bases__[:]

    # Remove Actor and ActorInterface bases before traverse
    found_actor_interface = False
    for cl_i in range(len(bases)):
        if bases[cl_i] is Actor:
            del bases[cl_i]
        if bases[cl_i] is ActorInterface:
            del bases[cl_i]
            found_actor_interface = True

    # cls is non actor parent node if cls does not inherit ActorInterface
    if not found_actor_interface: return cls

    # Traverse non-ActorInterface base types except for ActorInterface
    for cl in bases:
        non_actor_parent = get_non_actor_parent_type(cl)
        if non_actor_parent is not None:
            return non_actor_parent

    return None

def get_actor_interfaces(cls) -> list:
    """Get the list of the base classes that inherit :class:`ActorInterface`.
    
    :param object cls: The Actor object that inherit :class:`Actor` and
                       :class:`ActorInterfaces`
    :returns: the list of classes that inherit :class:`ActorInterface`
    :rtype: list
    """
    actor_bases = []
    for cl in cls.__bases__:
        if issubclass(cl, ActorInterface):
            if get_non_actor_parent_type(cl) is not None:
                continue
            actor_bases.append(cl)

    return actor_bases
