# -*- coding: utf-8 -*-

"""
Copyright (c) Microsoft Corporation.
Licensed under the MIT License.
"""

from abc import ABC


class ActorInterface(ABC):
    """A base class that Dapr Actor inherits.

    Actor requires to inherit ActorInterface as a base class.

    Example::

        class DaprActorInterface(ActorInterface):
            @actormethod('DoActorMethod1')
            async def do_actor_method1(self, param):
                ...

            @actormethod('DoActorMethod2')
            async def do_actor_method2(self, param):
                ...
    """
    ...


def actormethod(name: str = None):
    """Decorate actor method to define the method invoked by the remote actor.

    This allows users to call the decorated name via the proxy client.

    Example::

        class DaprActorInterface(ActorInterface):
            @actormethod(name='DoActorCall')
            async def do_actor_call(self, param):
                ...

    Args:
        name (str): the name of actor method.
    """
    def wrapper(funcobj):
        funcobj.__actormethod__ = name
        funcobj.__isabstractmethod__ = True
        return funcobj
    return wrapper
