# -*- coding: utf-8 -*-
# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

import threading

from dapr.actor.id import ActorId
from .actor import Actor
from .runtime_config import ActorRuntimeConfig
from .service import ActorService
from .typeinformation import ActorTypeInformation
from .manager import ActorManager
from dapr.serializers import Serializer

class ActorRuntime(object):
    """
    Register the types allows the runtime to create instances of the actor.

    Contains methods to register actor types.
    """

    _actor_config = ActorRuntimeConfig()

    _actor_managers = {}
    _actor_managers_lock = threading.RLock()

    @classmethod
    def set_actor_config(cls, config: ActorRuntimeConfig):
        cls._actor_config = config

    @classmethod
    def register_actor(
        cls,
        actor: Actor,
        message_serializer: Serializer):
        """
        Register an :class:`Actor` with the runtime.
        """

        actor_type_info = ActorTypeInformation(actor)
    
        actor_service = ActorService(actor_type_info, message_serializer)

        # Create an ActorManager, override existing entry if registered again.
        cls._actor_managers[actor_type_info.name] = ActorManager(actor_service)
    
    @classmethod
    def get_registered_actor_types(cls):
        return [actor_type for actor_type in cls._actor_managers.keys()]

    @classmethod
    def activate(cls, actor_type_name: str, actor_id: str):
        """
        Activate an actor for an actor type with given actor id.
        """
        
        cls.get_actor_manager(actor_type_name).activate_actor(ActorId(actor_id))

    @classmethod
    def deactivate(cls, actor_type_name: str, actor_id: str):
        """
        Deactivates an actor for an actor type with given actor id
        """

        cls.get_actor_manager(actor_type_name).deactivate_actor(ActorId(actor_id))


    @classmethod
    def dispatch(cls, actor_type_name: str, actor_id: str, actor_method_name: str, request_stream) -> bytes:
        
        return cls.get_actor_manager(actor_type_name).dispatch(ActorId(actor_id), actor_method_name, request_stream)

    @classmethod
    def get_actor_manager(cls, actor_type_name):
        with cls._actor_managers_lock:
            return cls._actor_managers.get(actor_type_name)

