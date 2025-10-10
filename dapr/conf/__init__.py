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
                val = self._coerce_env_value(default_value, env_variable)
                setattr(self, setting, val)
            else:
                setattr(self, setting, default_value)

    def __getattr__(self, name):
        if name not in dir(global_settings):
            raise AttributeError(f"'{self.__class__.__name__}' object has no attribute '{name}'")
        return getattr(self, name)

    @staticmethod
    def _coerce_env_value(default_value, env_variable: str):
        if default_value is None:
            return env_variable
        # Handle booleans explicitly to avoid bool('false') == True
        if isinstance(default_value, bool):
            s = env_variable.strip().lower()
            if s in ('1', 'true', 't', 'yes', 'y', 'on'):
                return True
            if s in ('0', 'false', 'f', 'no', 'n', 'off'):
                return False
            # Fallback: non-empty -> True for backward-compat
            return bool(s)
        # Integers
        if isinstance(default_value, int) and not isinstance(default_value, bool):
            return int(env_variable)
        # Floats
        if isinstance(default_value, float):
            return float(env_variable)
        # Other types: try to cast as before
        return type(default_value)(env_variable)


settings = Settings()
