# -*- coding: utf-8 -*-

"""
Copyright 2023 The Dapr Authors
Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at
    http://www.apache.org/licenses/LICENSE-2.0
Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
"""

import os

from dapr.conf import global_settings


class Settings:
    def __init__(self):
        for setting in dir(global_settings):
            default_value = getattr(global_settings, setting)
            env_variable = os.environ.get(setting)
            if env_variable:
                val = (
                    type(default_value)(env_variable) if default_value is not None else env_variable
                )
                setattr(self, setting, val)
            else:
                setattr(self, setting, default_value)

    def __getattr__(self, name):
        if name not in dir(global_settings):
            raise AttributeError(f"'{self.__class__.__name__}' object has no attribute '{name}'")
        return getattr(self, name)


settings = Settings()
