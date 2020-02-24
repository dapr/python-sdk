# -*- coding: utf-8 -*-

"""
Copyright (c) Microsoft Corporation.
Licensed under the MIT License.
"""

from dapr.actor.actor_interface import ActorInterface
from dapr.actor.id import ActorId
from dapr.actor.runtime import ActorMethodContext
from dapr.actor.runtime.typeutils import get_dispatchable_attrs_from_interface
from dapr.clients import DaprActorClientBase, DaprActorHttpClient

class ActorProxyFactory:
    """A factory class that creates :class:`ActorProxy` object to the remote
    actor objects.

    DefaultActorProxyFactory creates :class:`ActorProxy` with 
    :class:`DaprActorHttpClient` connecting to Dapr runtime.
    """

    def __init__(self):
        # TODO: support serializer for state store later
        self._dapr_client = DaprActorHttpClient()

    def create(self, actor_interface: ActorInterface,
               actor_type: str, actor_id: str) -> 'ActorProxy':
        return ActorProxy(self._dapr_client, actor_interface,
                          actor_type, actor_id)

class CallableProxy:
    def __init__(self, dapr_client: DaprActorClientBase,
                 actor_type: str, actor_id: ActorId, method: str):
        self._dapr_client = dapr_client
        self._actor_type = actor_type
        self._actor_id = actor_id
        self._method = method
    
    def __call__(self, *args, **kwargs) -> bytes:
        if len(args) > 1:
            raise ValueError('does not support multiple arguments')
        obj = None if len(args) == 0 else args[0]

        return self._dapr_client.invoke_method(
            self._actor_type, str(self._actor_id), self._method, obj)


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
            actor_type: str, actor_id: ActorId):
        self._dapr_client = client
        self._actor_id = actor_id
        self._actor_type = actor_type
        self._actor_interface = actor_interface
        self._dispatchable_attr = {}
        self._callable_proxies = {}

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

    def invoke(self, method: str, data: bytes=None) -> bytes:
        return self._dapr_client.invoke_actor_method(
            self._actor_type,
            str(self._actor_id),
            self.method,
            data)

    def __getattr__(self, name: str) -> CallableProxy:
        if name not in self._dispatchable_attr:
            get_dispatchable_attrs_from_interface(self._actor_interface, self._dispatchable_attr)
        
        attr_calltype = self._dispatchable_attr.get(name)
        if attr_calltype is None:
            raise AttributeError(f'{self._actor_interface.__class__} has no attribute {name}')

        if name not in self._callable_proxies:
            self._callable_proxies[name] = CallableProxy(
                self._dapr_client, self._actor_type,
                self._actor_id, name)
        
        return self._callable_proxies[name]
