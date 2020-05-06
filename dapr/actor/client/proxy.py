# -*- coding: utf-8 -*-

"""
Copyright (c) Microsoft Corporation.
Licensed under the MIT License.
"""

from typing import Any

from dapr.actor.actor_interface import ActorInterface
from dapr.actor.id import ActorId
from dapr.actor.runtime.typeutils import get_dispatchable_attrs_from_interface
from dapr.clients import DaprActorClientBase, DaprActorHttpClient
from dapr.serializers import Serializer, DefaultJSONSerializer


class ActorProxyFactory:
    """A factory class that creates :class:`ActorProxy` object to the remote
    actor objects.

    DefaultActorProxyFactory creates :class:`ActorProxy` with
    :class:`DaprActorHttpClient` connecting to Dapr runtime.
    """

    def __init__(self, message_serializer=DefaultJSONSerializer()):
        # TODO: support serializer for state store later
        self._dapr_client = DaprActorHttpClient()
        self._message_serializer = message_serializer

    def create(self, actor_interface: ActorInterface,
               actor_type: str, actor_id: str) -> 'ActorProxy':
        return ActorProxy(self._dapr_client, actor_interface,
                          actor_type, actor_id, self._message_serializer)


class CallableProxy:
    def __init__(
            self, proxy: 'ActorProxy', attr_calltype: dict,
            message_serializer: Serializer):
        self._proxy = proxy
        self._attr_calltype = attr_calltype
        self._message_serializer = message_serializer

    async def __call__(self, *args, **kwargs) -> Any:
        if len(args) > 1:
            raise ValueError('does not support multiple arguments')

        bytes_data = None
        if len(args) > 0:
            if isinstance(args[0], bytes):
                bytes_data = args[0]
            else:
                bytes_data = self._message_serializer.serialize(args[0])

        rtnval = await self._proxy.invoke(self._attr_calltype['actor_method'], bytes_data)

        return self._message_serializer.deserialize(rtnval, self._attr_calltype['return_types'])


class ActorProxy:
    """A remote proxy client that is proxy to the remote :class:`Actor`
    objects.

    :class:`ActorProxy` object is used for client-to-actor and actor-to-actor
    communication.
    """

    _default_proxy_factory = ActorProxyFactory()

    def __init__(
            self, client: DaprActorClientBase,
            actor_interface: ActorInterface,
            actor_type: str,
            actor_id: ActorId,
            message_serializer: Serializer):
        self._dapr_client = client
        self._actor_id = actor_id
        self._actor_type = actor_type
        self._actor_interface = actor_interface
        self._dispatchable_attr = {}
        self._callable_proxies = {}
        self._message_serializer = message_serializer

    @property
    def actor_id(self) -> ActorId:
        """Return ActorId"""
        return self._actor_id

    @property
    def actor_type(self) -> str:
        """Return actor type"""
        return self._actor_type

    @classmethod
    def create(
            cls, actor_interface: ActorInterface,
            actor_type: str, actor_id: ActorId,
            actor_proxy_factory=None) -> 'ActorProxy':
        factory = cls._default_proxy_factory if not actor_proxy_factory else actor_proxy_factory
        return factory.create(actor_interface, actor_type, actor_id)

    async def invoke(self, method: str, raw_body: bytes = None) -> bytes:
        """Invoke method """

        if raw_body is not None and not isinstance(raw_body, bytes):
            raise ValueError(f'raw_body {type(raw_body)} is not bytes type')

        return await self._dapr_client.invoke_method(
            self._actor_type, str(self._actor_id), method, raw_body)

    def __getattr__(self, name: str) -> CallableProxy:
        if name not in self._dispatchable_attr:
            get_dispatchable_attrs_from_interface(self._actor_interface, self._dispatchable_attr)

        attr_calltype = self._dispatchable_attr.get(name)
        if attr_calltype is None:
            raise AttributeError(f'{self._actor_interface.__class__} has no attribute {name}')

        if name not in self._callable_proxies:
            self._callable_proxies[name] = \
                CallableProxy(self, attr_calltype, self._message_serializer)

        return self._callable_proxies[name]
