# -*- coding: utf-8 -*-

"""
Copyright (c) Microsoft Corporation.
Licensed under the MIT License.
"""

from dapr.actor.actor_interface import ActorInterface, get_dispatchable_attrs
from dapr.actor.id import ActorId
from dapr.actor.runtime import ActorMethodContext
from dapr.clients import DaprActorClientBase, DaprActorHttpClient

class DefaultActorProxyFactory:
    """A factory class that creates :class:`ActorProxy` object to the remote
    actor objects.

    DefaultActorProxyFactory creates :class:`ActorProxy` with 
    :class:`DaprActorHttpClient` connecting to Dapr runtime.
    """

    def __init__(self):
        self._dapr_client = DaprActorHttpClient()

    def create(self, actor_interface: ActorInterface,
               actor_type: str, actor_id: str):
        return ActorProxy(self._dapr_client, actor_interface,
                          actor_type, actor_id)


class ActorProxy:
    """A remote proxy client that is proxy to the remote :class:`Actor`
    objects.

    :class:`ActorProxy` object is used for client-to-actor and actor-to-actor
    communication.
    """

    _default_proxy_factory = DefaultActorProxyFactory()

    def __init__(
            self, client: DaprActorClientBase,
            actor_interface: ActorInterface,
            actor_type: str, actor_id: str):
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
    def create(cls, actor_interface: ActorInterface,
               actor_type, actor_id):
        return cls._default_proxy_factory.create(
            actor_interface, actor_type, actor_id)

    def invoke(self, method: str, data: bytes=None) -> bytes:
        return self._dapr_client.invoke_actor_method(
            self._actor_type,
            str(self._actor_id),
            self.method,
            data)

    def __getattr__(self, name: str):
        if name not in self._dispatchable_attr:
            self._dispatchable_attr = get_dispatchable_attrs(self._actor_interface)
        
        attr_calltype = self._dispatchable_attr.get(name)
        if attr_calltype is None:
            raise AttributeError('{} has no attribute {!r}'.format(self._actor_interface.__class__, name))

        if name not in self._callable_proxies:
            self._callable_proxies[name] = CallableProxies(
                self._dapr_client, self._actor_type,
                self._actor_id, name)
        
        return self._callable_proxies[name]


class CallableProxies:
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
