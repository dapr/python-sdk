# -*- coding: utf-8 -*-

"""
Copyright (c) Microsoft Corporation.
Licensed under the MIT License.
"""

from dapr.actor.id import ActorId
from dapr.actor.runtime.state_provider import StateProvider
from dapr.clients import DaprActorClientBase
from dapr.serializers import Serializer

from typing import Callable, TYPE_CHECKING
if TYPE_CHECKING:
    from dapr.actor.runtime.actor import Actor
    from dapr.actor.runtime.type_information import ActorTypeInformation


class ActorRuntimeContext:
    """A context of ActorRuntime"""

    def __init__(
            self, actor_type_info: 'ActorTypeInformation',
            message_serializer: Serializer, state_serializer: Serializer,
            actor_client: DaprActorClientBase,
            actor_factory: Callable[['ActorRuntimeContext', ActorId], 'Actor'] = None):
        self._actor_type_info = actor_type_info
        self._actor_factory = actor_factory or self._default_actor_factory
        self._message_serializer = message_serializer
        self._state_serializer = state_serializer

        # Create State management provider for actor.
        self._dapr_client = actor_client
        self._state_provider: StateProvider = StateProvider(self._dapr_client, state_serializer)

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
        return self._state_provider

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

    def _default_actor_factory(
            self, ctx: 'ActorRuntimeContext', actor_id: ActorId) -> 'Actor':
        """Creates new Actor with actor_id.

        Args:
            ctx (:class:`ActorRuntimeContext`): the actor runtime context for new actor.
            actor_id (:class:`ActorId`): the actor id object.

        Returns:
            :class:`Actor`: new actor.
        """
        return self.actor_type_info.implementation_type(ctx, actor_id)
