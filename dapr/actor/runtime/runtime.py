# -*- coding: utf-8 -*-

"""
Copyright (c) Microsoft Corporation.
Licensed under the MIT License.
"""

import asyncio
import threading

from dapr.actor.id import ActorId
from dapr.actor.runtime.actor import Actor
from dapr.actor.runtime.config import ActorRuntimeConfig
from dapr.actor.runtime.context import ActorRuntimeContext
from dapr.actor.runtime.typeinformation import ActorTypeInformation
from dapr.actor.runtime.manager import ActorManager
from dapr.serializers import Serializer, DefaultJSONSerializer

class ActorRuntime:
    """Actor Runtime class that creates instances of :class:`Actor` and
    activates and deactivates :class:`Actor`.
    """

    _actor_config = ActorRuntimeConfig()

    _actor_managers = {}
    _actor_managers_lock = asyncio.Lock()

    @classmethod
    async def register_actor(
            cls, actor: Actor,
            message_serializer: Serializer = DefaultJSONSerializer(),
            state_serializer: Serializer = DefaultJSONSerializer()) -> None:
        """Register an :class:`Actor` with the runtime.

        :param Actor actor: Actor implementation
        :param Serializer message_serializer: Serializer that serializes message
            between actors.
        :param Serializer state_serializer: Serializer that serializes state values.
        """
        type_info = ActorTypeInformation.create(actor)
        ctx = ActorRuntimeContext(type_info, message_serializer, state_serializer)

        # Create an ActorManager, override existing entry if registered again.
        async with cls._actor_managers_lock:
            cls._actor_managers[type_info.type_name] = ActorManager(ctx)
            cls._actor_config.update_entities(ActorRuntime.get_registered_actor_types())

    @classmethod
    def get_registered_actor_types(cls) -> list:
        """Get registered actor types."""
        return [actor_type for actor_type in cls._actor_managers.keys()]

    @classmethod
    async def activate(cls, actor_type_name: str, actor_id: str) -> None:
        """Activate an actor for an actor type with given actor id.

        :param str actor_type_name: the name of actor type
        :param str actor_id: the actor id
        """
        manager = await cls._get_actor_manager(actor_type_name)
        await manager.activate_actor(ActorId(actor_id))

    @classmethod
    async def deactivate(cls, actor_type_name: str, actor_id: str) -> None:
        """Deactivates an actor for an actor type with given actor id.

        :param str actor_type_name: the name of actor type
        :param str actor_id: the actor id
        """
        manager = await cls._get_actor_manager(actor_type_name)
        await manager.deactivate_actor(ActorId(actor_id))

    @classmethod
    async def dispatch(
            cls, actor_type_name: str, actor_id: str,
            actor_method_name: str, request_body: bytes) -> bytes:
        """Dispatch actor method defined in actor_type.
        
        :param str actor_type_name: the name of actor type
        :param str actor_id: Actor ID
        :param str actor_method_name: the method name that is dispatched
        :param bytes request_body: the body of request that is passed to actor method arguments
        :returns: serialized response
        :rtype: bytes
        """
        manager = await cls._get_actor_manager(actor_type_name)
        return await manager.dispatch(ActorId(actor_id), actor_method_name, request_body)

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
    async def _get_actor_manager(cls, actor_type_name: str):
        async with cls._actor_managers_lock:
            return cls._actor_managers.get(actor_type_name)
