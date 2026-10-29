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
import logging
import re
from typing import Callable, Dict, List, Optional, Type, Union

from dapr.actor.id import ActorId
from dapr.actor.runtime._type_information import ActorTypeInformation
from dapr.actor.runtime.actor import Actor
from dapr.actor.runtime.config import ActorRuntimeConfig
from dapr.actor.runtime.context import ActorRuntimeContext
from dapr.actor.runtime.manager import ActorManager
from dapr.clients.base import DaprActorClientBase
from dapr.clients.http.dapr_actor_http_client import DaprActorHttpClient
from dapr.common.reentrancy_context import reentrancy_ctx
from dapr.conf import _FromSettings
from dapr.serializers import DefaultJSONSerializer, Serializer

_HTTP_TIMEOUT_FROM_SETTINGS = _FromSettings('DAPR_HTTP_TIMEOUT_SECONDS')

# Older sidecars forward caller headers, so a caller could spoof the activation id.
_MIN_ACTIVATION_ID_VERSION = (1, 19, 1)
_VERSION_LOOKUP_TIMEOUT_SECONDS = 5

logger = logging.getLogger(__name__)


def _supports_activation_id(version: str) -> bool:
    match = re.match(r'(\d+)\.(\d+)\.(\d+)(?:[-+].*)?$', version)
    if match is None:
        return False
    return tuple(int(part) for part in match.groups()) >= _MIN_ACTIVATION_ID_VERSION


class ActorRuntime:
    """The class that creates instances of :class:`Actor` and
    activates and deactivates :class:`Actor`.
    """

    _actor_config = ActorRuntimeConfig()

    _actor_managers: Dict[str, ActorManager] = {}
    _actor_managers_lock = asyncio.Lock()

    _activation_id_trusted: Optional[bool] = None
    _version_lookup: Optional['asyncio.Future[str]'] = None

    @classmethod
    async def register_actor(
        cls,
        actor: Type[Actor],
        message_serializer: Serializer = DefaultJSONSerializer(),
        state_serializer: Serializer = DefaultJSONSerializer(),
        http_timeout_seconds: Union[int, None, _FromSettings] = _HTTP_TIMEOUT_FROM_SETTINGS,
        actor_factory: Optional[Callable[['ActorRuntimeContext', ActorId], 'Actor']] = None,
        actor_client: Optional[DaprActorClientBase] = None,
    ) -> None:
        """Registers an :class:`Actor` object with the runtime.

        Args:
            actor (:class:`Actor`): Actor implementation.
            message_serializer (:class:`Serializer`): A serializer that serializes message
                between actors.
            state_serializer (:class:`Serializer`): Serializer that serializes state values.
            http_timeout_seconds (int, optional): timeout for the default HTTP actor client.
                Defaults to ``DAPR_HTTP_TIMEOUT_SECONDS``, read when the actor is registered.
            actor_factory (Callable, optional): factory to create Actor objects.
            actor_client (:class:`DaprActorClientBase`, optional): the client used for the
                actor's outbound operations (state, reminders, timers, invocations).
                Defaults to the HTTP client; :class:`ActorGrpcHost` supplies a gRPC one.
        """
        type_info = ActorTypeInformation.create(actor)
        if isinstance(http_timeout_seconds, _FromSettings):
            http_timeout_seconds = int(http_timeout_seconds.resolve())
        if actor_client is None:
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
        activation_id: Optional[str] = None,
    ) -> bytes:
        """Dispatches actor method defined in actor_type.

        Args:
            actor_type_name (str): the name of actor type.
            actor_id (str): Actor ID.
            actor_method_name (str): the method name that is dispatched.
            request_body (bytes): the body of request that is passed to actor method arguments.
            reentrancy_id (str): reentrancy ID obtained from the dapr_reentrancy_id header
                if present.
            activation_id (str, optional): the Dapr-Actor-Activation-Id header value.

        Returns:
            bytes: serialized response data.

        Raises:
            ValueError: `actor_type_name` actor type is not registered.
        """
        reentrancy_ctx.set(reentrancy_id)
        manager = await cls._get_actor_manager(actor_type_name)
        if not manager:
            raise ValueError(f'{actor_type_name} is not registered.')
        activation_id = await cls._trusted_activation_id(manager, activation_id)
        return await manager.dispatch(
            ActorId(actor_id), actor_method_name, request_body, activation_id
        )

    @classmethod
    async def fire_reminder(
        cls,
        actor_type_name: str,
        actor_id: str,
        name: str,
        state: bytes,
        activation_id: Optional[str] = None,
    ) -> None:
        """Fires a reminder for the Actor.

        Args:
            actor_type_name (str): the name of actor type.
            actor_id (str): Actor ID.
            name (str): the name of reminder.
            state (bytes): the body of request that is passed to reminder callback.
            activation_id (str, optional): the Dapr-Actor-Activation-Id header value.

        Raises:
            ValueError: `actor_type_name` actor type is not registered.
        """

        manager = await cls._get_actor_manager(actor_type_name)
        if not manager:
            raise ValueError(f'{actor_type_name} is not registered.')
        activation_id = await cls._trusted_activation_id(manager, activation_id)
        await manager.fire_reminder(ActorId(actor_id), name, state, activation_id)

    @classmethod
    async def fire_timer(
        cls,
        actor_type_name: str,
        actor_id: str,
        name: str,
        state: bytes,
        activation_id: Optional[str] = None,
    ) -> None:
        """Fires a timer for the Actor.

        Args:
            actor_type_name (str): the name of actor type.
            actor_id (str): Actor ID.
            name (str): the timer's name.
            state (bytes): the timer's trigger body.
            activation_id (str, optional): the Dapr-Actor-Activation-Id header value.

        Raises:
            ValueError: `actor_type_name` actor type is not registered.
        """
        manager = await cls._get_actor_manager(actor_type_name)
        if not manager:
            raise ValueError(f'{actor_type_name} is not registered.')
        activation_id = await cls._trusted_activation_id(manager, activation_id)
        await manager.fire_timer(ActorId(actor_id), name, state, activation_id)

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

    @classmethod
    async def _trusted_activation_id(
        cls, manager: ActorManager, activation_id: Optional[str]
    ) -> Optional[str]:
        """Returns activation_id only when the sidecar is new enough to set it itself."""
        if not activation_id:
            return activation_id
        if cls._activation_id_trusted is None:
            lookup = cls._version_lookup
            if lookup is None or lookup.get_loop() is not asyncio.get_running_loop():
                lookup = asyncio.ensure_future(
                    asyncio.wait_for(
                        manager._runtime_ctx.dapr_client.get_runtime_version(),
                        _VERSION_LOOKUP_TIMEOUT_SECONDS,
                    )
                )
                cls._version_lookup = lookup
            try:
                version = await asyncio.shield(lookup)
            except Exception as exception:  # noqa: BLE001
                if cls._version_lookup is lookup:
                    cls._version_lookup = None
                logger.warning(
                    'Ignoring actor activation id, sidecar version lookup failed: %r', exception
                )
                return None
            cls._activation_id_trusted = _supports_activation_id(version)
        return activation_id if cls._activation_id_trusted else None
