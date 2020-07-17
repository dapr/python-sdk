# -*- coding: utf-8 -*-

"""
Copyright (c) Microsoft Corporation.
Licensed under the MIT License.
"""

from typing import Any, Dict, Optional, Union

from google.protobuf.any_pb2 import Any as GrpcAny
from google.protobuf.message import Message as GrpcMessage

from dapr.clients.base import DEFAULT_JSON_CONTENT_TYPE
from dapr.clients.grpc._helpers import MetadataDict, MetadataTuple, tuple_to_dict, unpack


class InvokeServiceRequest:
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

    HTTP_METHODS = [
        'GET',
        'HEAD',
        'POST',
        'PUT',
        'DELETE',
        'CONNECT',
        'OPTIONS',
        'TRACE'
    ]

    def __init__(
            self,
            data: Optional[Any] = None,
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
        self._content_type = content_type
        self._http_verb = None
        self._http_querystring: Dict[str, str] = {}

        self.data = data
        if not content_type and not self.is_proto():
            self.content_type = DEFAULT_JSON_CONTENT_TYPE

    @property
    def metadata(self) -> MetadataDict:
        """Returns headers tuple as a dict."""
        return self.get_metadata(as_dict=True)

    def get_metadata(self, as_dict: Optional[bool] = False) -> Union[MetadataDict, MetadataTuple]:
        if as_dict:
            return tuple_to_dict(self._metadata)
        return self._metadata

    @metadata.setter
    def metadata(self, val: MetadataTuple) -> None:
        self._metadata = val

    @property
    def http_verb(self) -> str:
        return self._http_verb
    
    @http_verb.setter
    def http_verb(self, val: str) -> None:
        if val not in self.InvokeServiceRequest.HTTP_METHODS:
            raise ValueError(f'{val} is the invalid HTTP verb.')
        self._http_verb = val

    @property
    def http_querystring(self) -> Dict[str, str]:
        return self._http_querystring

    def is_http(self) -> bool:
        return hasattr(self, '_http_verb') and not (not self._http_verb)

    @property
    def proto(self) -> GrpcAny:
        return self._data

    @proto.setter
    def proto(self, val: GrpcMessage) -> None:
        if not isinstance(val, GrpcMessage):
            raise ValueError(f'invalid data type')
        self._data = GrpcAny()
        self._data.Pack(val)
        self._content_type = None

    def is_proto(self) -> bool:
        return hasattr(self, '_data') and self._data.type_url

    def unpack(self, message: GrpcMessage) -> None:
        """Unpack the serialized protocol buffer message.

        Args:
            message (:obj:`google.protobuf.message.Message`): the protocol buffer message object
                to which the response data is deserialized.

        Raises:
            ValueError: message is not protocol buffer message object or message's type is not
                matched with the response data type
        """
        unpack(self.proto, message)

    @property
    def data(self) -> bytes:
        if self.is_proto():
            raise ValueError('data is protocol buffer message object.')
        return self._data.value
    
    @data.setter
    def data(self, val: Any) -> None:
        if val is None:
            return
        if isinstance(val, str):
            val = val.encode('utf-8')
        if isinstance(val, bytes):
            self._data = GrpcAny(value=val)
        elif isinstance(val, GrpcAny):
            self._data = val
            self.content_type = None
        elif isinstance(val, GrpcMessage):
            self.proto = val
        else:
            raise ValueError(f'invalid data type {type(val)}')

    @property
    def text(self) -> str:
        return self.data.decode('utf-8')

    @property
    def content_type(self) -> Optional[str]:
        return self._content_type

    @content_type.setter
    def content_type(self, val: str) -> None:
        self._content_type = val
