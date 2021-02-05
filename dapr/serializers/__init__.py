# -*- coding: utf-8 -*-

"""
Copyright (c) Microsoft Corporation and Dapr Contributors.
Licensed under the MIT License.
"""

from dapr.serializers.base import Serializer
from dapr.serializers.json import DefaultJSONSerializer

__all__ = [
    'Serializer',
    'DefaultJSONSerializer'
]
