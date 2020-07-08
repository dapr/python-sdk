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
    """A request data representation for invoke_service API.

    This stores the request data with the proper serialization. This seralizes
    data to :obj:`google.protobuf.any_pb2.Any` if data is the type of protocol
    buffer message.

    Attributes:
        data (:obj:`google.protobuf.any_pb2.Any`): the serialized data for
            invoke_service request.
        content_type (str, optional): the content type of data which is valid
            only for bytes array data.
    """
    def __init__(
            self,
            data: Union[bytes, str, GrpcMessage],
            content_type: Optional[str] = None):
        """Inits InvokeServiceRequestData with data and content_type.

        Args:
            data (bytes, str, or :obj:`google.protobuf.message.Message`): the data
                which is used for invoke_service request.
            content_type (str): the content_type of data when the data is bytes.
                The default content type is application/json.

        Raises:
            ValueError: data is not bytes or :obj:`google.protobuf.message.Message`.
        """
        self._data = GrpcAny()

        if isinstance(data, str):
            data = data.encode('utf-8')

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
    def data(self) -> GrpcAny:
        return self._data

    @property
    def content_type(self) -> Optional[str]:
        return self._content_type
