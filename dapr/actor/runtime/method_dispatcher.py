# -*- coding: utf-8 -*-

"""
Copyright (c) Microsoft Corporation.
Licensed under the MIT License.
"""

from dapr.actor.runtime.actor import Actor
from dapr.actor.runtime.typeinformation import ActorTypeInformation
from dapr.actor.actor_interface import get_dispatchable_attrs

class ActorMethodDispatcher:
    def __init__(self, type_info: ActorTypeInformation):
        self._dispatch_mapping = get_dispatchable_attrs(type_info.implementation_type)

    def get_params(self, name: str) -> dict:
        if name not in self._dispatch_mapping:
            raise AttributeError(
                f'no method {name} is in dispatch mapping')

        return self._dispatch_mapping[name].params

    def dispatch(self, actor: Actor, name: str, *args, **kwargs):
        if name not in self._dispatch_mapping:
            raise AttributeError(
                f'type object {self.__class__.__name__} has no method {name}')

        return getattr(actor, self._dispatch_mapping[name].method_name)(*args, **kwargs)
