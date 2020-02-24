# -*- coding: utf-8 -*-

"""
Copyright (c) Microsoft Corporation.
Licensed under the MIT License.
"""

import io
import threading

from dapr.actor.id import ActorId
from dapr.actor.runtime.actor import Actor
from dapr.actor.runtime.runtime_config import ActorRuntimeConfig
from dapr.actor.runtime.runtime_context import ActorRuntimeContext
from dapr.actor.runtime.typeinformation import ActorTypeInformation
from dapr.actor.runtime.manager import ActorManager
from dapr.serializers import Serializer, DefaultJSONSerializer

class ActorRuntime:
    """Actor Runtime class that creates instances of :class:`Actor` and
    activates and deactivates :class:`Actor`.
    """

    _actor_config = ActorRuntimeConfig()

    _actor_managers = {}
    _actor_managers_lock = threading.RLock()

    @classmethod
    def register_actor(
            cls, actor: Actor,
            message_serializer: Serializer=DefaultJSONSerializer()) -> None:
        """Register an :class:`Actor` with the runtime.

        :param Actor actor: Actor implementation
        :param Serializer message_serializer: Serializer that serializes message
            between actors.
        """
        type_info = ActorTypeInformation.create(actor)    
        ctx = ActorRuntimeContext(type_info, message_serializer)

        # Create an ActorManager, override existing entry if registered again.
        with cls._actor_managers_lock:
            cls._actor_managers[type_info.type_name] = ActorManager(ctx)
            cls._actor_config.update_entities(ActorRuntime.get_registered_actor_types())
    
    @classmethod
    def get_registered_actor_types(cls) -> list:
        """Get registered actor types."""
        return [actor_type for actor_type in cls._actor_managers.keys()]

    @classmethod
    def activate(cls, actor_type_name: str, actor_id: str) -> None:
        """Activate an actor for an actor type with given actor id.
        
        :param str actor_type_name: the name of actor type
        :param str actor_id: the actor id
        """
        cls._get_actor_manager(actor_type_name).activate_actor(ActorId(actor_id))

    @classmethod
    def deactivate(cls, actor_type_name: str, actor_id: str) -> None:
        """Deactivates an actor for an actor type with given actor id.
        
        :param str actor_type_name: the name of actor type
        :param str actor_id: the actor id
        """
        cls._get_actor_manager(actor_type_name).deactivate_actor(ActorId(actor_id))

    @classmethod
    def dispatch(
            cls, actor_type_name: str, actor_id: str,
            actor_method_name: str, request_stream: io.IOBase) -> bytes:
        return cls._get_actor_manager(actor_type_name).dispatch(
            ActorId(actor_id), actor_method_name, request_stream)

    @classmethod
    def set_actor_config(cls, config: ActorRuntimeConfig) -> None:
        """Set actor runtime config

        :param ActorRuntimeConfig config: The config to set up actor runtime
        """
        cls._actor_config = config
        cls._actor_config.update_entities(ActorRuntime.get_registered_actor_types())
    
    @classmethod
    def get_actor_config(cls) -> ActorRuntimeConfig:
        return cls._actor_config

    @classmethod
    def _get_actor_manager(cls, actor_type_name: str):
        with cls._actor_managers_lock:
            return cls._actor_managers.get(actor_type_name)
