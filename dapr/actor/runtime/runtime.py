# -*- coding: utf-8 -*-

"""
Copyright (c) Microsoft Corporation.
Licensed under the MIT License.
"""

import threading

from dapr.actor.id import ActorId
from dapr.actor.runtime.actor import Actor
from dapr.actor.runtime.runtime_config import ActorRuntimeConfig
from dapr.actor.runtime.service import ActorService
from dapr.actor.runtime.typeinformation import ActorTypeInformation
from dapr.actor.runtime.manager import ActorManager
from dapr.serializers import Serializer

class ActorRuntime:
    """Actor Runtime implementation that creates instances of :class:`Actor` and
    activates and deactivates :class:`Actor`.
    """

    _actor_config = ActorRuntimeConfig()

    _actor_managers = {}
    _actor_managers_lock = threading.RLock()

    @classmethod
    def set_actor_config(cls, config: ActorRuntimeConfig):
        cls._actor_config = config

    @classmethod
    def register_actor(cls, actor: Actor, message_serializer: Serializer) -> None:
        """
        Register an :class:`Actor` with the runtime.
        """

        actor_type_info = ActorTypeInformation(actor)    
        actor_service = ActorService(actor_type_info, message_serializer)
        # Create an ActorManager, override existing entry if registered again.
        cls._actor_managers[actor_type_info.name] = ActorManager(actor_service)
    
    @classmethod
    def get_registered_actor_types(cls) -> None:
        return [actor_type for actor_type in cls._actor_managers.keys()]

    @classmethod
    def activate(cls, actor_type_name: str, actor_id: str) -> None:
        """Activate an actor for an actor type with given actor id."""
        
        cls._get_actor_manager(actor_type_name).activate_actor(ActorId(actor_id))

    @classmethod
    def deactivate(cls, actor_type_name: str, actor_id: str) -> None:
        """Deactivates an actor for an actor type with given actor id."""

        cls._get_actor_manager(actor_type_name).deactivate_actor(ActorId(actor_id))


    @classmethod
    def dispatch(cls, actor_type_name: str, actor_id: str,
            actor_method_name: str, request_stream) -> bytes:        
        return cls._get_actor_manager(actor_type_name).dispatch(ActorId(actor_id),
            actor_method_name, request_stream)

    @classmethod
    def _get_actor_manager(cls, actor_type_name: str):
        with cls._actor_managers_lock:
            return cls._actor_managers.get(actor_type_name)
