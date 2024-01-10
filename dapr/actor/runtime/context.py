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

from dapr.actor.id import ActorId
from dapr.actor.runtime._state_provider import StateProvider
from dapr.clients.base import DaprActorClientBase
from dapr.serializers import Serializer

from typing import Callable, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from dapr.actor.runtime.actor import Actor
    from dapr.actor.runtime._type_information import ActorTypeInformation


class ActorRuntimeContext:
    """A context of ActorRuntime.

    This defines the context of actor runtime, which carries the type information of Actor,
    the serializers for invocation and state, and the actor clients for Dapr runtime.

    Attributes:
        actor_type_info(:class:`ActorTypeInformation`): the type information to initiate
            Actor object.
        message_serializer(:class:`Serializer`): the serializer for actor invocation request
            and response body.
        state_serializer(:class:`Serializer`): the seralizer for state value.
        state_provider(:class:`StateProvider`): the provider which is the adapter used
            for state manager.
        dapr_client(:class:`DaprActorClientBase`): the actor client used for dapr runtime.
    """

    def __init__(
        self,
        actor_type_info: 'ActorTypeInformation',
        message_serializer: Serializer,
        state_serializer: Serializer,
        actor_client: DaprActorClientBase,
        actor_factory: Optional[Callable[['ActorRuntimeContext', ActorId], 'Actor']] = None,
    ):
        """Creates :class:`ActorRuntimeContext` object.

        Args:
            actor_type_info(:class:`ActorTypeInformation`): the type information to initiate
                Actor object.
            message_serializer(:class:`Serializer`): the serializer for actor invocation
                request and response body.
            state_serializer(:class:`Serializer`): the seralizer for state value.
            actor_client(:class:`DaprActorClientBase`): the actor client used for dapr runtime.
            actor_factory(Callable, optional): the factory to create Actor object by
                actor_type_info.
        """
        self._actor_type_info = actor_type_info
        self._actor_factory = actor_factory or self._default_actor_factory
        self._message_serializer = message_serializer
        self._state_serializer = state_serializer

        # Create State management provider for actor.
        self._dapr_client = actor_client
        self._provider: StateProvider = StateProvider(self._dapr_client, state_serializer)

    @property
    def actor_type_info(self) -> 'ActorTypeInformation':
        """Return :class:`ActorTypeInformation` in this context."""
        return self._actor_type_info

    @property
    def message_serializer(self) -> Serializer:
        """Return message serializer which is used for Actor invocation."""
        return self._message_serializer

    @property
    def state_serializer(self) -> Serializer:
        """Return state serializer which is used for State value."""
        return self._state_serializer

    @property
    def state_provider(self) -> StateProvider:
        """Return state provider to manage actor states."""
        return self._provider

    @property
    def dapr_client(self) -> DaprActorClientBase:
        """Return dapr client."""
        return self._dapr_client

    def create_actor(self, actor_id: ActorId) -> 'Actor':
        """Create the object of :class:`Actor` for :class:`ActorId`.

        Args:
            actor_id (:class:`ActorId`): ActorId object representing :class:`ActorId`

        Returns:
            :class:`Actor`: new actor.
        """
        return self._actor_factory(self, actor_id)

    def _default_actor_factory(self, ctx: 'ActorRuntimeContext', actor_id: ActorId) -> 'Actor':
        """Creates new Actor with actor_id.

        Args:
            ctx (:class:`ActorRuntimeContext`): the actor runtime context for new actor.
            actor_id (:class:`ActorId`): the actor id object.

        Returns:
            :class:`Actor`: new actor.
        """
        return self.actor_type_info.implementation_type(ctx, actor_id)
