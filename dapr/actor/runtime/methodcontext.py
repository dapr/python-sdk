# -*- coding: utf-8 -*-
# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

from .calltype import ActorCallType

class ActorMethodContext(object):
    """
    Contains information about the method that is invoked by actor runtime
    """    
    _call_type: ActorCallType

    def __init__(self, method_name: str, call_type: ActorCallType):
        self._method_name = method_name
        self._call_type = call_type

    @property
    def method_name(self) -> str:
        return self._method_name

    @property
    def call_type(self) -> ActorCallType:
        return self._call_type

    @classmethod
    def create_for_actor(cls, method_name: str):
        return ActorMethodContext(method_name, ActorCallType.actor_interface_method)