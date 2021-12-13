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
