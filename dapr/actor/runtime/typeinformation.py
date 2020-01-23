# -*- coding: utf-8 -*-
# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

class ActorTypeInformation(object):
    """
    """

    def __init__(self, actor):
        self._implType = actor

    @property
    def name(self):
        return self._implType.__name__

    @property
    def implementation_type(self):
        return self._implType
