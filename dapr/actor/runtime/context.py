# -*- coding: utf-8 -*-

"""
Copyright (c) Microsoft Corporation.
Licensed under the MIT License.
"""

from dapr.actor.id import ActorId
from dapr.actor.runtime.stateprovider import StateProvider
from dapr.clients import DaprActorClientBase, DaprActorHttpClient
from dapr.serializers import Serializer

from typing import Callable

class ActorRuntimeContext:
    """A context of ActorRuntime"""

    def __init__(
            self, actor_type_info: 'ActorTypeInformation',
            message_serializer: Serializer, state_serializer: Serializer,
            actor_client: DaprActorClientBase = None,
            actor_factory: Callable[['ActorRuntimeContext', ActorId], 'Actor'] = None):
        self._actor_type_info = actor_type_info
        self._actor_factory = actor_factory or self._default_actor_factory
        self._message_serializer = message_serializer
        self._state_serializer = state_serializer

        # Create State management provider for actor.
        self._dapr_client = actor_client or DaprActorHttpClient()
        self._state_provider = StateProvider(self._dapr_client, state_serializer)

    @property
    def actor_type_info(self) -> 'ActorTypeInformation':
        """Return :class:`ActorTypeInformation`"""
        return self._actor_type_info

    @property
    def message_serializer(self) -> Serializer:
        """Return message serializer which is used for Actor method invocation."""
        return self._message_serializer

    @property
    def state_serializer(self) -> Serializer:
        """Return state serializer which is used for State value."""
        return self._state_serializer

    @property
    def state_provider(self) -> Serializer:
        """Return state provider to manage actor states."""
        return self._state_provider

    @property
    def dapr_client(self) -> DaprActorClientBase:
        """Return dapr client."""
        return self._dapr_client

    def create_actor(self, actor_id: ActorId) -> 'Actor':
        """Create the object of :class:`Actor` for :class:`ActorId`

        :param actor_id: ActorId object representing :class:`ActorId`
        :rtype: :class:`Actor` object
        """
        return self._actor_factory(self, actor_id)

    def _default_actor_factory(
            self, ctx: 'ActorRuntimeContext', actor_id: ActorId) -> 'Actor':
        # Create the actor object for actor_type_info and actor_id
        return self.actor_type_info.implementation_type(ctx, actor_id)
