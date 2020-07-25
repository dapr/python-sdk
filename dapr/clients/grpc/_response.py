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


class DaprResponse:
    """A base class for Dapr Response.

    This is the base class for Dapr Response. User can gets the headers and trailers as
    a dict.

    Attributes:
        headers(dict): A dict to include the headers from Dapr gRPC Response.
    """

    def __init__(
            self,
            headers: MetadataTuple = ()):
        """Inits DapResponse with headers and trailers.

        Args:
            headers (tuple, optional): the tuple for the headers from response
        """
        self.headers = headers

    @property
    def headers(self) -> MetadataDict:
        """Returns headers tuple as a dict."""
        return self.get_headers(as_dict=True)

    def get_headers(self, as_dict: Optional[bool] = False) -> Union[MetadataDict, MetadataTuple]:
        """Gets headers from the response.
        
        Args:
            as_dict (bool): dict type headers if as_dict is True. Otherwise, return
                tuple headers.
        
        Returns:
            dict or tuple: response headers.
        """
        if as_dict:
            return tuple_to_dict(self._headers)
        return self._headers

    @headers.setter
    def headers(self, val: MetadataTuple) -> None:
        """Set response headers."""
        self._headers = val


class InvokeServiceResponse(DaprResponse):
    """The response of invoke_service API.

    This inherits from DaprResponse and has the helpers to handle bytes array
    and protocol buffer data.

    Attributes:
        data (:obj:`google.protobuf.any_pb2.Any`): the serialized protocol
            buffer raw message
        content (bytes): bytes data if response data is not serialized
            protocol buffer message
        content_type (str): the type of `content`
    """
    def __init__(
            self,
            data: Any = None,
            content_type: Optional[str] = None,
            headers: Optional[MetadataTuple] = ()):
        """Initializes InvokeServiceReponse from :obj:`common_v1.InvokeResponse`.

        Args:
            data (:obj:`google.protobuf.any_pb2.Any`): the response data from Dapr response
            content_type (str, optional): the content type of the bytes data
            headers (Tuple, optional): the headers from Dapr gRPC response

        Raises:
            ValueError: if the response data is not :class:`google.protobuf.any_pb2.Any`
                object.
        """
        super(InvokeServiceResponse, self).__init__(headers)
        self._content_type = content_type
        self.headers = headers
        self.data = data
        if not content_type and not self.is_proto():
            self.content_type = DEFAULT_JSON_CONTENT_TYPE

    @property
    def proto(self) -> GrpcAny:
        """Gets raw serialized protocol buffer message.

        Raises:
            ValueError: data is not protocol buffer message object
        """
        return self._data

    @proto.setter
    def proto(self, val: GrpcMessage) -> None:
        if not isinstance(val, GrpcMessage):
            raise ValueError('invalid data type')
        self._data = GrpcAny()
        self._data.Pack(val)
        self._content_type = None

    def is_proto(self) -> bool:
        """Returns True if the response data is the serialized protocol buffer message."""
        return hasattr(self, '_data') and self._data.type_url

    @property
    def data(self) -> bytes:
        """Gets raw bytes data if the response data content is not serialized
        protocol buffer message.

        Raises:
            ValueError: the response data is the serialized protocol buffer message
        """
        if self.is_proto():
            raise ValueError('data is protocol buffer message object.')
        return self._data.value

    @data.setter
    def data(self, val: Any) -> None:
        if val is None:
            return
        if isinstance(val, str):
            val = val.encode('utf-8')
        if isinstance(val, (bytes, str)):
            self._data = GrpcAny(value=val)
        elif isinstance(val, GrpcAny):
            self._data = val
        elif isinstance(val, GrpcMessage):
            self.proto = val
        else:
            raise ValueError(f'invalid data type {type(val)}')

    def text(self) -> str:
        """Gets content as str if the response data content is not serialized
        protocol buffer message.

        Raises:
            ValueError: the response data is the serialized protocol buffer message
        """
        return self.data.decode('utf-8')

    @property
    def content_type(self) -> Optional[str]:
        """Gets the content type of content attribute."""
        return self._content_type

    @content_type.setter
    def content_type(self, val: str) -> None:
        self._content_type = val

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


class BindingResponse(DaprResponse):
    """The response of invoke_binding API.

    This inherits from DaprResponse and has the helpers to handle bytes array data.

    Attributes:
        data (bytes): the data in response from the invoke_binding call
        binding_metadata (Dict[str, str]): metadata sent as a reponse by the binding
    """
    def __init__(
            self,
            data: Union[bytes, str],
            binding_metadata: Optional[Dict[str, str]] = {},
            headers: Optional[MetadataTuple] = ()):
        """Initializes InvokeBindingReponse from :obj:`runtime_v1.InvokeBindingResponse`.

        Args:
            data (bytes): the data in response from the invoke_binding call
            binding_metadata (Dict[str, str]): metadata sent as a reponse by the binding
            headers (Tuple, optional): the headers from Dapr gRPC response

        Raises:
            ValueError: if the response data is not :class:`google.protobuf.any_pb2.Any`
                object.
        """
        super(BindingResponse, self).__init__(headers)
        self.data = data
        self._metadata = binding_metadata

    def text(self) -> str:
        """Gets content as str."""
        return self._data.decode('utf-8')

    @property
    def data(self) -> bytes:
        """Gets raw bytes data."""
        return self._data

    @data.setter
    def data(self, val: Union[bytes, str]) -> None:
        if not isinstance(val, (bytes, str)):
            raise ValueError(f'data type is invalid {type(val)}')
        if isinstance(val, str):
            val = val.encode('utf-8')
        self._data = val

    @property
    def binding_metadata(self) -> Dict[str, str]:
        """Gets the metadata in the response."""
        return self._metadata


class GetSecretResponse(DaprResponse):
    """The response of get_secret API.

    This inherits from DaprResponse

    Attributes:
        secret (Dict[str, str]): secret received from response
    """
    def __init__(
            self,
            secret: Dict[str, str],
            headers: Optional[MetadataTuple] = ()):
        """Initializes GetSecretReponse from :obj:`dapr_v1.GetSecretResponse`.

        Args:
            secret (Dict[Str, str]): the secret from Dapr response
            headers (Tuple, optional): the headers from Dapr gRPC response

        """
        super(GetSecretResponse, self).__init__(headers)
        self._secret = secret

    @property
    def secret(self) -> Dict[str, str]:
        """Gets secret as a dict
        """
        return self._secret
