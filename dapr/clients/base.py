# -*- coding: utf-8 -*-

"""
Copyright (c) Microsoft Corporation.
Licensed under the MIT License.
"""

from abc import ABC, abstractmethod

class DaprActorClientBase(ABC):
    """A base class that represents Dapr Actor Client.

    TODO: add actor client api iteratively
    """

    @abstractmethod
    async def invoke_method(
            self, actor_type: str, actor_id: str,
            method: str, data: bytes) -> bytes:
        ...
