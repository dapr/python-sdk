# -*- coding: utf-8 -*-

"""
Copyright (c) Microsoft Corporation.
Licensed under the MIT License.
"""

from abc import ABC, abstractmethod
from typing import Callable

class Serializer(ABC):
    """
    Abstract serializer base class
    """

    @abstractmethod
    def serialize(
        self, obj: object,
        custom_hook: Callable[[object], bytes]) -> bytes:
        pass

    @abstractmethod
    def deserialize(
        self, data: bytes,
        custom_hook: Callable[[object], bytes]) -> object:
        pass
