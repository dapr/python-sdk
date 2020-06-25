# -*- coding: utf-8 -*-

"""
Copyright (c) Microsoft Corporation.
Licensed under the MIT License.
"""

from abc import ABC, abstractmethod
from typing import Dict, Optional

from google.protobuf.any_pb2 import Any as GrpcAny


DEFAULT_ENCODING = 'utf-8'
DEFAULT_JSON_CONTENT_TYPE = f'application/json; charset={DEFAULT_ENCODING}'

class DaprActorClientBase(ABC):
    """A base class that represents Dapr Actor Client.
    """

    @abstractmethod
    async def invoke_method(
            self, actor_type: str, actor_id: str,
            method: str, data: Optional[bytes] = None) -> bytes:
        ...

    @abstractmethod
    async def save_state_transactionally(
            self, actor_type: str, actor_id: str,
            data: bytes) -> None:
        ...

    @abstractmethod
    async def get_state(
            self, actor_type: str, actor_id: str, name: str) -> bytes:
        ...

    @abstractmethod
    async def register_reminder(
            self, actor_type: str, actor_id: str, name: str, data: bytes) -> None:
        ...

    @abstractmethod
    async def unregister_reminder(
            self, actor_type: str, actor_id: str, name: str) -> None:
        ...

    @abstractmethod
    async def register_timer(
            self, actor_type: str, actor_id: str, name: str, data: bytes) -> None:
        ...

    @abstractmethod
    async def unregister_timer(
            self, actor_type: str, actor_id: str, name: str) -> None:
        ...


class DaprClientBase(ABC):
    """A base class that represents Dapr Actor Client.
    """

    @abstractmethod
    def invoke_service(
            self,
            target_id: str,
            method: str,
            data: Union[bytes, Any],
            content_type: Optional[str] = DEFAULT_JSON_CONTENT_TYPE,
            metadata: Optional[Dict[str, str]] = None,
            http_verb: Optional[str] = None,
            http_querystring: Optional[Dict[str, str]] = None) -> Tuple[Union[bytes, GrpcAny], Dict[str, str]]:
        """Invoke target_id service to call method.

        :param str target_id: str to represent target App ID.
        :param str method: str to represent method name defined in target_id
        :param Union[bytes, Message] data: bytes or Message for data which will send to target_id
        :param str content_type: str to represent content_type of data if data is bytes type
        :param Dict[str, str] metadata: dict to pass custom metadata to target app
        :param str http_verb: http method verb to call HTTP callee application
        :param Dict[str, str] http_querystring: dict to represent querystring for HTTP callee application
    
        :returns: the response from actor
        :rtype: Union[bytes, Any]
        """
        ...
