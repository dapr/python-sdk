# -*- coding: utf-8 -*-

"""
Copyright (c) Microsoft Corporation and Dapr Contributors.
Licensed under the MIT License.
"""

from abc import ABC, abstractmethod
from typing import Any, Callable, Optional, Type


class Serializer(ABC):
    """Serializer base class."""

    @abstractmethod
    def serialize(
            self, obj: object,
            custom_hook: Optional[Callable[[object], bytes]] = None) -> bytes:
        ...

    @abstractmethod
    def deserialize(
            self, data: bytes, data_type: Optional[Type] = object,
            custom_hook: Optional[Callable[[bytes], object]] = None) -> Any:
        ...
