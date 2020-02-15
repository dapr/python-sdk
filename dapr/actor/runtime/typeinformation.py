# -*- coding: utf-8 -*-

"""
Copyright (c) Microsoft Corporation.
Licensed under the MIT License.
"""

class ActorTypeInformation:
    """
    """

    def __init__(self, actor):
        self._impl_type = actor

    @property
    def name(self):
        return self._impl_type.__name__

    @property
    def implementation_type(self):
        return self._impl_type
