# -*- coding: utf-8 -*-

"""
Copyright (c) Microsoft Corporation.
Licensed under the MIT License.
"""

from .version import __version__

from dapr.clients import DaprClient

__all__ = [
    '__version__',
    'DaprClient',
]
