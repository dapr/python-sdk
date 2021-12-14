# -*- coding: utf-8 -*-

"""
Copyright 2021 The Dapr Authors
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

from abc import ABC, abstractmethod
from typing import Any, Callable, Dict, Optional, Type

from dapr.actor.actor_interface import ActorInterface
from dapr.actor.id import ActorId
from dapr.actor.runtime._type_utils import get_dispatchable_attrs_from_interface
from dapr.clients import DaprActorClientBase, DaprActorHttpClient
from dapr.serializers import Serializer, DefaultJSONSerializer
from dapr.conf import settings

# Actor factory Callable type hint.
ACTOR_FACTORY_CALLBACK = Callable[[ActorInterface, str, str], 'ActorProxy']


class ActorFactoryBase(ABC):
    @abstractmethod
    def create(
            self, actor_type: str, actor_id: ActorId,
            actor_interface: Type[ActorInterface] = None) -> 'ActorProxy':
        ...


class ActorProxyFactory(ActorFactoryBase):
    """A factory class that creates :class:`ActorProxy` object to the remote
    actor objects.

    DefaultActorProxyFactory creates :class:`ActorProxy` with
    :class:`DaprActorHttpClient` connecting to Dapr runtime.
    """

    def __init__(
            self,
            message_serializer=DefaultJSONSerializer(),
            http_timeout_seconds: int = settings.DAPR_HTTP_TIMEOUT_SECONDS):
        # TODO: support serializer for state store later
        self._dapr_client = DaprActorHttpClient(message_serializer, timeout=http_timeout_seconds)
        self._message_serializer = message_serializer

    def create(
            self, actor_type: str, actor_id: ActorId,
            actor_interface: Type[ActorInterface] = None) -> 'ActorProxy':
        return ActorProxy(
            self._dapr_client, actor_type, actor_id,
            actor_interface, self._message_serializer)


class CallableProxy:
    def __init__(
            self, proxy: 'ActorProxy', attr_call_type: Dict[str, Any],
            message_serializer: Serializer):
        self._proxy = proxy
        self._attr_call_type = attr_call_type
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

        rtnval = await self._proxy.invoke_method(self._attr_call_type['actor_method'], bytes_data)

        return self._message_serializer.deserialize(rtnval, self._attr_call_type['return_types'])


class ActorProxy:
    """A remote proxy client that is proxy to the remote :class:`Actor`
    objects.

    :class:`ActorProxy` object is used for client-to-actor and actor-to-actor
    communication.
    """

    _default_proxy_factory = ActorProxyFactory()

    def __init__(
            self, client: DaprActorClientBase,
            actor_type: str,
            actor_id: ActorId,
            actor_interface: Optional[Type[ActorInterface]],
            message_serializer: Serializer):
        self._dapr_client = client
        self._actor_id = actor_id
        self._actor_type = actor_type
        self._actor_interface = actor_interface
        self._message_serializer = message_serializer

        self._dispatchable_attr: Dict[str, Dict[str, Any]] = {}
        self._callable_proxies: Dict[str, CallableProxy] = {}

    @property
    def actor_id(self) -> ActorId:
        """Returns ActorId."""
        return self._actor_id

    @property
    def actor_type(self) -> str:
        """Returns actor type."""
        return self._actor_type

    @classmethod
    def create(
            cls,
            actor_type: str, actor_id: ActorId,
            actor_interface: Type[ActorInterface] = None,
            actor_proxy_factory: Optional[ActorFactoryBase] = None) -> 'ActorProxy':
        """Creates ActorProxy client to call actor.

        Args:
            actor_type (str): the name of actor type.
            actor_id (str): the id of actor.
            actor_interface (:class:`ActorInterface`, optional): the actor interface derived from
                :class:`ActorInterface`.
            actor_proxy_factor (Callable, optional): the actor factory callable.

        Returns:
            :class:`ActorProxy': new Actor Proxy client.
        """
        factory = cls._default_proxy_factory if not actor_proxy_factory else actor_proxy_factory
        return factory.create(actor_type, actor_id, actor_interface)

    async def invoke_method(self, method: str, raw_body: Optional[bytes] = None) -> bytes:
        """Invokes actor method.

        This is the non-rpc style actor method invocation. It needs to serialize
        the request object and deserialize the response body.

        If the client has Actor interface, it is recommended to use RPC style actor
        invocation.

        Args:
            method (str): the method defined in actor.
            raw_body (bytes): the request body which will be sent to actor.

        Returns:
            bytes: the response from actor method.
        """

        if raw_body is not None and not isinstance(raw_body, bytes):
            raise ValueError(f'raw_body {type(raw_body)} is not bytes type')

        return await self._dapr_client.invoke_method(
            self._actor_type, str(self._actor_id), method, raw_body)

    def __getattr__(self, name: str) -> CallableProxy:
        """Enables RPC style actor method invocation.

        Args:
            name (str): the name of method

        Returns:
            :class:`CallableProxy`: the callable object to invoke actor method
                like a RPC method call.

        Raises:
            ValueError: actor_interface is not given.
            AttributeError: method is not defined in Actor interface.
        """
        if not self._actor_interface:
            raise ValueError('actor_interface is not set. use invoke method.')

        if name not in self._dispatchable_attr:
            get_dispatchable_attrs_from_interface(self._actor_interface, self._dispatchable_attr)

        attr_call_type = self._dispatchable_attr.get(name)
        if attr_call_type is None:
            raise AttributeError(f'{self._actor_interface.__class__} has no attribute {name}')

        if name not in self._callable_proxies:
            self._callable_proxies[name] = CallableProxy(
                self, attr_call_type, self._message_serializer)

        return self._callable_proxies[name]
