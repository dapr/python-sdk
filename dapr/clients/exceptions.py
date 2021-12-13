# -*- coding: utf-8 -*-

"""
Copyright 2021 The Dapr Authors
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

from typing import Optional

ERROR_CODE_UNKNOWN = "UNKNOWN"
ERROR_CODE_DOES_NOT_EXIST = "ERR_DOES_NOT_EXIST"


class DaprInternalError(Exception):
    """DaprInternalError encapsulates all Dapr exceptions"""
    def __init__(
            self, message: Optional[str],
            error_code: Optional[str] = ERROR_CODE_UNKNOWN):
        self._message = message
        self._error_code = error_code

    def as_dict(self):
        return {
            'message': self._message,
            'errorCode': self._error_code,
        }
