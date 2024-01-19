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

from typing import Union
import logging


class LoggerOptions:
    def __init__(
        self,
        log_level: Union[str, None] = None,
        log_handler: Union[logging.Handler, None] = None,
        log_formatter: Union[logging.Formatter, None] = None,
    ):
        # Set default log level to INFO if none is provided
        if log_level is None:
            log_level = logging.INFO
        # Add a default log handler if none is provided
        if log_handler is None:
            log_handler = logging.StreamHandler()
        # Set a default log formatter if none is provided
        if log_formatter is None:
            log_formatter = logging.Formatter(
                fmt='%(asctime)s.%(msecs)03d %(name)s %(levelname)s: %(message)s',
                datefmt='%Y-%m-%d %H:%M:%S',
            )
        self.log_level = log_level
        self.log_handler = log_handler
        self.log_formatter = log_formatter
