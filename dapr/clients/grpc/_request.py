# -*- coding: utf-8 -*-

"""
Copyright (c) Microsoft Corporation.
Licensed under the MIT License.
"""

from typing import Optional, Union, Dict

from dapr.clients.grpc._helpers import MetadataTuple
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


class InvokeBindingRequestData:
    """A request data representation for invoke_binding API.

    This stores the request data and metadata with the proper serialization.
    This seralizes data to bytes and metadata to a dictionary of key value pairs.

    Attributes:
        data (bytes, str): the data which is used for invoke_binding request.
        metadata (Dict[str, str]): the metadata sent to the binding.
    """
    def __init__(
            self,
            data: Union[bytes, str],
            metadata: Optional[MetadataTuple] = ()):
        """Inits InvokeBindingRequestData with data and metadata if given.

        Args:
            data (bytes, str): the data which is used for invoke_binding request.
            metadata (MetadataTuple, optional): the metadata to be sent to the binding.

        Raises:
            ValueError: data is not bytes or str.
            ValueError: metadata values are not str.
        """
        self._metadata = dict()
        for item in metadata:   # type: ignore
            if not isinstance(item[1], str):
                raise ValueError(f'invalid metadata value type {type(item[1])}')
            self._metadata[str(item[0])] = str(item[1])
        self._data = b''
        if isinstance(data, str):
            self._data = data.encode('utf-8')
        elif isinstance(data, bytes):
            self._data = data
        else:
            raise ValueError(f'invalid data type {type(data)}')

    @property
    def data(self) -> bytes:
        return self._data

    @property
    def metadata(self) -> Dict[str, str]:
        return self._metadata
