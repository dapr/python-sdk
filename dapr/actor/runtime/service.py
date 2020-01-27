# -*- coding: utf-8 -*-
# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

from dapr.actor import Actor, ActorId
from dapr.actor.runtime.typeinformation import ActorTypeInformation
from dapr.serializers import Serializer

class ActorService(object):
    """
    Represent a host for an actor type within the actor runtime
    """

    def __init__(
        self,
        actor_type_info: ActorTypeInformation,
        message_serializer: Serializer,
        actor_factory = None):
        
        self._actor_type_info = actor_type_info
        self._message_serializer = message_serializer
        self._actor_factory = actor_factory or self._default_actor_factory

    @property
    def actor_type_info(self) -> ActorTypeInformation:
        return self._actor_type_info
    
    @property
    def message_serializer(self) -> Serializer:
        return self._message_serializer

    def create_actor(self, actor_id: ActorId) -> Actor:
        return self._actor_factory(self, actor_id)
    
    def _default_actor_factory(self, actor_service: ActorService, actor_id: ActorId) -> Actor:
        return self.actor_type_info.implementation_type(actor_service, actor_id)