# -*- coding: utf-8 -*-

"""
Copyright (c) Microsoft Corporation.
Licensed under the MIT License.
"""

from typing import Optional, Union

from google.protobuf.any_pb2 import Any as GrpcAny
from google.protobuf.message import Message as GrpcMessage

from dapr.clients.base import DEFAULT_JSON_CONTENT_TYPE


class InvokeServiceRequestData:
    def __init__(
            self,
            data: Union[bytes, GrpcMessage],
            content_type: Optional[str] = None):
        self._data = GrpcAny()
        if isinstance(data, bytes):
            self._data.value = data
            self._content_type = content_type
            if not content_type:
                self._content_type = DEFAULT_JSON_CONTENT_TYPE
        elif isinstance(data, GrpcMessage):
            self._data.Pack(data)
            self._content_type = None
        else:
            raise ValueError(f'invalid data type {type(data)}')

    @property
    def proto(self) -> GrpcAny:
        return self._data

    @property
    def content_type(self) -> Optional[str]:
        return self._content_type
