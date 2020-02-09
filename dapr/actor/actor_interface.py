# -*- coding: utf-8 -*-
# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

from abc import ABC
from dapr.actor.runtime.methodcontext import ActorMethodContext

class ActorInterface(ABC):
    @classmethod
    def get_dispatchable_attrs(cls):
        # Find all user actor interfaces derived from ActorInterface
        actor_interfaces = []
        for cl in cls.mro():
            if cl.__base__ == ActorInterface:
                actor_interfaces.append(cl)        
        # Find all dispatchable attributes
        dispatch_map = {}
        for user_actor_cls in actor_interfaces:
            for attr, v in user_actor_cls.__dict__.items():
                if attr.startswith('_') or not callable(v):
                    continue
                actor_method_name = getattr(v, '__actormethod__') if hasattr(v, '__actormethod__') else attr
                dispatch_map[actor_method_name] = ActorMethodContext.create_for_actor(attr)

        return dispatch_map

def actormethod(name=None):
    def wrapper(funcobj):
        funcobj.__actormethod__ = name
        funcobj.__isabstractmethod__ = True
        return funcobj
    return wrapper
