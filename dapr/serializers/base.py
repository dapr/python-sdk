# -*- coding: utf-8 -*-
# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

from abc import ABC, abstractmethod

class Serializer(ABC):
    """
    Abstract serializer base class
    """

    @abstractmethod
    def serialize(self, data: object):
        pass

    @abstractmethod
    def deserialize(self, data, type) -> object:
        pass