# -*- coding: utf-8 -*-

"""
Copyright (c) Microsoft Corporation.
Licensed under the MIT License.
"""

from typing import Dict, Optional, Union, Sequence

from google.protobuf.any_pb2 import Any as GrpcAny
from google.protobuf.message import Message as GrpcMessage

from dapr.clients.base import DEFAULT_JSON_CONTENT_TYPE
from dapr.clients.grpc._helpers import (
    MetadataDict,
    MetadataTuple,
    to_bytes,
    to_str,
    tuple_to_dict,
    unpack,
)


class DaprResponse:
    """A base class for Dapr Response.

    This is the base class for Dapr Response. User can get the headers as a dict.

    Attributes:
        headers(dict): A dict to include the headers from Dapr gRPC Response.
    """

    def __init__(
            self,
            headers: MetadataTuple = ()):
        """Inits DapResponse with headers and trailers.

        Args:
            headers (tuple, optional): the tuple for the headers from response.
        """
        self.headers = headers  # type: ignore

    @property
    def headers(self) -> MetadataDict:
        """Gets headers as a dict."""
        return self.get_headers(as_dict=True)  # type: ignore

    @headers.setter
    def headers(self, val: MetadataTuple) -> None:
        """Sets response headers."""
        self._headers = val

    def get_headers(self, as_dict: bool = False) -> Union[MetadataDict, MetadataTuple]:
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


class InvokeServiceResponse(DaprResponse):
    """The response of invoke_service API.

    This inherits from DaprResponse and has the helpers to handle bytes array
    and protocol buffer data.

    Attributes:
        headers (tuple, optional): the tuple for the headers from response.
        data (str, bytes, GrpcAny, GrpcMessage, optional): the serialized protocol
            buffer raw message
        content (bytes, optional): bytes data if response data is not serialized
            protocol buffer message
        content_type (str, optional): the type of `content`
    """

    def __init__(
            self,
            data: Union[str, bytes, GrpcAny, GrpcMessage, None] = None,
            content_type: Optional[str] = None,
            headers: MetadataTuple = ()):
        """Initializes InvokeServiceReponse from :obj:`common_v1.InvokeResponse`.

        Args:
            data (str, bytes, GrpcAny, GrpcMessage, optional): the response data
                from Dapr response
            content_type (str, optional): the content type of the bytes data
            headers (tuple, optional): the headers from Dapr gRPC response
        """
        super(InvokeServiceResponse, self).__init__(headers)
        self._content_type = content_type

        self.set_data(data)

        # Set content_type to application/json type if content_type
        # is not given and date is bytes or str type.
        if not self.is_proto() and not content_type:
            self.content_type = DEFAULT_JSON_CONTENT_TYPE

    @property
    def proto(self) -> GrpcAny:
        """Gets raw serialized protocol buffer message.

        Raises:
            ValueError: data is not protocol buffer message object
        """
        return self._data

    def is_proto(self) -> bool:
        """Returns True if the response data is the serialized protocol buffer message."""
        return hasattr(self, '_data') and self._data.type_url != ''

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
    def data(self, val: Union[str, bytes]) -> None:
        """Sets str or bytes type data to request data."""
        self.set_data(val)

    def set_data(self, val: Union[str, bytes, GrpcAny, GrpcMessage, None]) -> None:
        """Sets data to request data."""
        if val is None:
            self._data = GrpcAny()
        elif isinstance(val, (bytes, str)):
            self._data = GrpcAny(value=to_bytes(val))
        elif isinstance(val, (GrpcAny, GrpcMessage)):
            self.pack(val)
        else:
            raise ValueError(f'invalid data type {type(val)}')

    def text(self) -> str:
        """Gets content as str if the response data content is not serialized
        protocol buffer message.

        Raises:
            ValueError: the response data is the serialized protocol buffer message
        """
        return to_str(self.data)

    @property
    def content_type(self) -> Optional[str]:
        """Gets the content type of content attribute."""
        return self._content_type

    @content_type.setter
    def content_type(self, val: Optional[str]) -> None:
        """Sets content type for bytes data."""
        self._content_type = val

    def pack(self, val: Union[GrpcAny, GrpcMessage]) -> None:
        """Serializes protocol buffer message.

        Args:
            message (:class:`GrpcMessage`, :class:`GrpcAny`): the protocol buffer message object

        Raises:
            ValueError: message is neither GrpcAny nor GrpcMessage.
        """
        if isinstance(val, GrpcAny):
            self._data = val
        elif isinstance(val, GrpcMessage):
            self._data = GrpcAny()
            self._data.Pack(val)
        else:
            raise ValueError('invalid data type')

    def unpack(self, message: GrpcMessage) -> None:
        """Deserializes the serialized protocol buffer message.

        Args:
            message (:class:`GrpcMessage`): the protocol buffer message object
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
            binding_metadata: Dict[str, str] = {},
            headers: MetadataTuple = ()):
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
        self.data = data  # type: ignore
        self._metadata = binding_metadata

    def text(self) -> str:
        """Gets content as str."""
        return to_str(self._data)

    @property
    def data(self) -> bytes:
        """Gets raw bytes data."""
        return self._data

    @data.setter
    def data(self, val: Union[bytes, str]) -> None:
        """Sets str or bytes type data to request data."""
        self._data = to_bytes(val)

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
            headers: MetadataTuple = ()):
        """Initializes GetSecretReponse from :obj:`dapr_v1.GetSecretResponse`.

        Args:
            secret (Dict[Str, str]): the secret from Dapr response
            headers (Tuple, optional): the headers from Dapr gRPC response
        """
        super(GetSecretResponse, self).__init__(headers)
        self._secret = secret

    @property
    def secret(self) -> Dict[str, str]:
        """Gets secret as a dict."""
        return self._secret


class StateResponse(DaprResponse):
    """The response of get_state API.

    This inherits from DaprResponse

    Attributes:
        data (Dict[str, str]): secret received from response
    """

    def __init__(
            self,
            data: Union[bytes, str],
            headers: MetadataTuple = ()):
        """Initializes StateResponse from :obj:`runtime_v1.GetStateResponse`.

        Args:
            data (bytes): the data in response from the get_state call
            headers (Tuple, optional): the headers from Dapr gRPC response

        Raises:
            ValueError: if the response data is not :class:`google.protobuf.any_pb2.Any`
                object.
        """
        super(StateResponse, self).__init__(headers)
        self.data = data  # type: ignore

    def text(self) -> str:
        """Gets content as str."""
        return to_str(self._data)

    @property
    def data(self) -> bytes:
        """Gets raw bytes data."""
        return self._data

    @data.setter
    def data(self, val: Union[bytes, str]) -> None:
        """Sets str or bytes type data to request data."""
        self._data = to_bytes(val)


class BulkStateItem:
    """A state item from bulk_get_state API.

    Attributes:
        key (str): state's key.
        data (Union[bytes, str]): state's data.
        etag (str): state's etag.
        error (str): error when state was retrieved
    """

    def __init__(
            self,
            key: str,
            data: Union[bytes, str],
            etag: str = '',
            error: str = ''):
        """Initializes BulkStateItem item from :obj:`runtime_v1.BulkStateItem`.

        Args:
            key (str): state's key.
            data (Union[bytes, str]): state's data.
            etag (str): state's etag.
            error (str): error when state was retrieved
        """
        self._key = key
        self._data = data  # type: ignore
        self._etag = etag
        self._error = error

    def text(self) -> str:
        """Gets content as str."""
        return to_str(self._data)

    @property
    def key(self) -> str:
        """Gets key."""
        return self._key

    @property
    def data(self) -> Union[bytes, str]:
        """Gets raw data."""
        return self._data

    @property
    def etag(self) -> str:
        """Gets etag."""
        return self._etag

    @property
    def error(self) -> str:
        """Gets error."""
        return self._error


class BulkStatesResponse(DaprResponse):
    """The response of bulk_get_state API.

    This inherits from DaprResponse

    Attributes:
        data (Union[bytes, str]): state's data.
    """

    def __init__(
            self,
            items: Sequence[BulkStateItem],
            headers: MetadataTuple = ()):
        """Initializes BulkStatesResponse from :obj:`runtime_v1.GetBulkStateResponse`.

        Args:
            items (Sequence[BulkStatesItem]): the items retrieved.
            headers (Tuple, optional): the headers from Dapr gRPC response.
        """
        super(BulkStatesResponse, self).__init__(headers)
        self._items = items

    @property
    def items(self) -> Sequence[BulkStateItem]:
        """Gets the items."""
        return self._items
