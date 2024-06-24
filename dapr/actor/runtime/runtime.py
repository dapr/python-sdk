# -*- coding: utf-8 -*-

"""
Copyright 2023 The Dapr Authors
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

import asyncio

from typing import Dict, List, Optional, Type, Callable

from dapr.actor.id import ActorId
from dapr.actor.runtime.actor import Actor
from dapr.actor.runtime.config import ActorRuntimeConfig
from dapr.actor.runtime.context import ActorRuntimeContext
from dapr.actor.runtime._type_information import ActorTypeInformation
from dapr.actor.runtime.manager import ActorManager
from dapr.clients.http.dapr_actor_http_client import DaprActorHttpClient
from dapr.serializers import Serializer, DefaultJSONSerializer
from dapr.conf import settings

from dapr.actor.runtime.reentrancy_context import reentrancy_ctx


class ActorRuntime:
    """The class that creates instances of :class:`Actor` and
    activates and deactivates :class:`Actor`.
    """

    _actor_config = ActorRuntimeConfig()

    _actor_managers: Dict[str, ActorManager] = {}
    _actor_managers_lock = asyncio.Lock()

    @classmethod
    async def register_actor(
        cls,
        actor: Type[Actor],
        message_serializer: Serializer = DefaultJSONSerializer(),
        state_serializer: Serializer = DefaultJSONSerializer(),
        http_timeout_seconds: int = settings.DAPR_HTTP_TIMEOUT_SECONDS,
        actor_factory: Optional[Callable[['ActorRuntimeContext', ActorId], 'Actor']] = None,
    ) -> None:
        """Registers an :class:`Actor` object with the runtime.

        Args:
            actor (:class:`Actor`): Actor implementation.
            message_serializer (:class:`Serializer`): A serializer that serializes message
                between actors.
            state_serializer (:class:`Serializer`): Serializer that serializes state values.
            http_timeout_seconds (:int:): a configurable timeout value
        """
        type_info = ActorTypeInformation.create(actor)
        # TODO: We will allow to use gRPC client later.
        actor_client = DaprActorHttpClient(message_serializer, timeout=http_timeout_seconds)
        ctx = ActorRuntimeContext(
            type_info, message_serializer, state_serializer, actor_client, actor_factory
        )

        # Create an ActorManager, override existing entry if registered again.
        async with cls._actor_managers_lock:
            cls._actor_managers[type_info.type_name] = ActorManager(ctx)
            cls._actor_config.update_entities(ActorRuntime.get_registered_actor_types())

    @classmethod
    def get_registered_actor_types(cls) -> List[str]:
        """Gets registered actor types."""
        return [actor_type for actor_type in cls._actor_managers.keys()]

    @classmethod
    async def deactivate(cls, actor_type_name: str, actor_id: str) -> None:
        """Deactivates an actor for an actor type with given actor id.

        Args:
            actor_type_name (str): the name of actor type.
            actor_id (str): the actor id.

        Raises:
            ValueError: `actor_type_name` actor type is not registered.
        """
        manager = await cls._get_actor_manager(actor_type_name)
        if not manager:
            raise ValueError(f'{actor_type_name} is not registered.')
        await manager.deactivate_actor(ActorId(actor_id))

    @classmethod
    async def dispatch(
        cls,
        actor_type_name: str,
        actor_id: str,
        actor_method_name: str,
        request_body: bytes,
        reentrancy_id: Optional[str] = None,
    ) -> bytes:
        """Dispatches actor method defined in actor_type.

        Args:
            actor_type_name (str): the name of actor type.
            actor_id (str): Actor ID.
            actor_method_name (str): the method name that is dispatched.
            request_body (bytes): the body of request that is passed to actor method arguments.
            reentrancy_id (str): reentrancy ID obtained from the dapr_reentrancy_id header
                if present.

        Returns:
            bytes: serialized response data.

        Raises:
            ValueError: `actor_type_name` actor type is not registered.
        """
        reentrancy_ctx.set(reentrancy_id)
        manager = await cls._get_actor_manager(actor_type_name)
        if not manager:
            raise ValueError(f'{actor_type_name} is not registered.')
        return await manager.dispatch(ActorId(actor_id), actor_method_name, request_body)

    @classmethod
    async def fire_reminder(
        cls, actor_type_name: str, actor_id: str, name: str, state: bytes
    ) -> None:
        """Fires a reminder for the Actor.

        Args:
            actor_type_name (str): the name of actor type.
            actor_id (str): Actor ID.
            name (str): the name of reminder.
            state (bytes): the body of request that is passed to reminder callback.

        Raises:
            ValueError: `actor_type_name` actor type is not registered.
        """

        manager = await cls._get_actor_manager(actor_type_name)
        if not manager:
            raise ValueError(f'{actor_type_name} is not registered.')
        await manager.fire_reminder(ActorId(actor_id), name, state)

    @classmethod
    async def fire_timer(cls, actor_type_name: str, actor_id: str, name: str, state: bytes) -> None:
        """Fires a timer for the Actor.

        Args:
            actor_type_name (str): the name of actor type.
            actor_id (str): Actor ID.
            name (str): the timer's name.
            state (bytes): the timer's trigger body.

        Raises:
            ValueError: `actor_type_name` actor type is not registered.
        """
        manager = await cls._get_actor_manager(actor_type_name)
        if not manager:
            raise ValueError(f'{actor_type_name} is not registered.')
        await manager.fire_timer(ActorId(actor_id), name, state)

    @classmethod
    def set_actor_config(cls, config: ActorRuntimeConfig) -> None:
        """Sets actor runtime config

        Args:
            config (:class:`ActorRuntimeConfig`): The config to set up actor runtime
        """
        cls._actor_config = config
        cls._actor_config.update_entities(ActorRuntime.get_registered_actor_types())

    @classmethod
    def get_actor_config(cls) -> ActorRuntimeConfig:
        """Gets :class:`ActorRuntimeConfig`."""
        return cls._actor_config

    @classmethod
    async def _get_actor_manager(cls, actor_type_name: str) -> Optional[ActorManager]:
        """Gets :class:`ActorManager` object for actor_type_name.

        Args:
            actor_type_name (str): the type name of actor.

        Returns:
            :class:`ActorManager`: an actor manager object for actor_type_name actor.
        """
        async with cls._actor_managers_lock:
            return cls._actor_managers.get(actor_type_name)
