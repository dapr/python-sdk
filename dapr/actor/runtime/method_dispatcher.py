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

    def dispatch(self, actor: Actor, name: str, *args, **kwargs):
        self._check_name_exist(name)
        return getattr(actor, self._dispatch_mapping[name].method_name)(*args, **kwargs)

    def get_arg_names(self, name: str) -> list:
        self._check_name_exist(name)
        return self._dispatch_mapping[name].arg_names

    def get_arg_types(self, name: str) -> list:
        self._check_name_exist(name)
        return self._dispatch_mapping[name].arg_types

    def get_return_type(self, name: str) -> type:
        self._check_name_exist(name)
        return self._dispatch_mapping[name].return_types
    
    def _check_name_exist(self, name: str):
        if name not in self._dispatch_mapping:
            raise AttributeError(
                f'type object {self.__class__.__name__} has no method {name}')
