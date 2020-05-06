# -*- coding: utf-8 -*-

"""
Copyright (c) Microsoft Corporation.
Licensed under the MIT License.
"""

import os

from dapr.conf import global_settings


class Settings:
    def __init__(self):
        for setting in dir(global_settings):
            default_value = getattr(global_settings, setting)
            env_variable = os.environ.get(setting)
            setattr(self, setting, env_variable or default_value)

    def __getattr__(self, name):
        return getattr(self, name)


settings = Settings()
