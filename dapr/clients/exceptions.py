# -*- coding: utf-8 -*-

"""
Copyright (c) Microsoft Corporation and Dapr Contributors.
Licensed under the MIT License.
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
