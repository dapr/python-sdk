# -*- coding: utf-8 -*-

"""
Copyright (c) Microsoft Corporation.
Licensed under the MIT License.
"""

from abc import ABC, abstractmethod
from typing import Callable

class Serializer(ABC):
    """Serializer base class."""

    @abstractmethod
    def serialize(
        self, obj: object,
        custom_hook: Callable[[object], bytes]) -> bytes:
        ...

    @abstractmethod
    def deserialize(
        self, data: bytes, data_type: type,
        custom_hook: Callable[[bytes], object]) -> object:
        ...
