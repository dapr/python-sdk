# -*- coding: utf-8 -*-

"""
Copyright (c) Microsoft Corporation.
Licensed under the MIT License.
"""

from abc import ABC
from dapr.actor.runtime.methodcontext import ActorMethodContext

class ActorInterface(ABC):
    """A base class that Dapr Actor inherits.

    Actor requires to inherit ActorInterface as a base class.
    
    Example::

        class DaprActor(ActorInterface):
            def do_actor_method1(self, param):
                ...

            def do_actor_method2(self, param):
                ...
    """
    ...

def actormethod(name: str=None):
    """Decorate actor method to define the method invoked by the remote actor.
    
    This allows users to call the decorated name via the proxy client.

    Example::

        class DaprActor(ActorInterface):
            @actormethod(name='DoActorCall')
            def do_actor_call(self, param):
                ...

    """
    def wrapper(funcobj):
        funcobj.__actormethod__ = name
        funcobj.__isabstractmethod__ = True
        return funcobj
    return wrapper

def get_dispatchable_attrs(actor: object) -> dict:
    """Get the list of dispatchable attributes from actor.

    :param object actor: The actor object which inherits :class:`ActorInterface`
    :returns: The map from attribute to actor method
    :rtype: dict
    """
    # Find all user actor interfaces derived from ActorInterface
    actor_interfaces = []
    for cl in actor.mro():
        if cl.__base__ == ActorInterface:
            actor_interfaces.append(cl)
    
    if len(actor_interfaces):
        raise ValueError(f'{actor.__name__} has not inherited from ActorInterface')

    # Find all dispatchable attributes
    dispatch_map = {}
    for user_actor_cls in actor_interfaces:
        for attr, v in user_actor_cls.__dict__.items():
            if attr.startswith('_') or not callable(v):
                continue
            actor_method_name = getattr(v, '__actormethod__') if hasattr(v, '__actormethod__') else attr
            dispatch_map[actor_method_name] = ActorMethodContext.create_for_actor(attr)

    return dispatch_map
