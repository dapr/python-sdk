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
    """Settings resolved from the environment each time they are read.

    A value assigned on the instance (``settings.DAPR_HTTP_PORT = 3500``) takes
    precedence; otherwise the ``DAPR_*`` environment variable is used when set,
    falling back to the default in :mod:`dapr.conf.global_settings`.
    """

    def __getattr__(self, name):
        # Only reached when the attribute was not assigned on the instance.
        if name.startswith('__') or not hasattr(global_settings, name):
            raise AttributeError(f"'{self.__class__.__name__}' object has no attribute '{name}'")
        default_value = getattr(global_settings, name)
        env_variable = os.environ.get(name)
        if not env_variable:
            return default_value
        if default_value is None:
            return env_variable
        try:
            return type(default_value)(env_variable)
        except ValueError as error:
            raise ValueError(f'Invalid value for {name}: {env_variable!r}') from error

    def __dir__(self):
        return sorted(
            {*super().__dir__(), *(n for n in dir(global_settings) if not n.startswith('__'))}
        )


settings = Settings()
