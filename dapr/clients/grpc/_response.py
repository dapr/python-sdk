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

import json


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


class InvokeMethodResponse(DaprResponse):
    """The response of invoke_method API.

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
        """Initializes InvokeMethodReponse from :obj:`common_v1.InvokeResponse`.

        Args:
            data (str, bytes, GrpcAny, GrpcMessage, optional): the response data
                from Dapr response
            content_type (str, optional): the content type of the bytes data
            headers (tuple, optional): the headers from Dapr gRPC response
        """
        super(InvokeMethodResponse, self).__init__(headers)
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

    def json(self) -> Dict[str, object]:
        """Gets the content as json if the response data content is not a serialized
        protocol buffer message.

        Returns:
            str: [description]
        """
        return json.loads(to_str(self.data))

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

        if self.content_type is not None and self.content_type.lower() == "application/x-protobuf":
            message.ParseFromString(self.data)
            return

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

    def json(self) -> Dict[str, object]:
        """Gets content as deserialized JSON dictionary."""
        return json.loads(to_str(self._data))

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


class GetBulkSecretResponse(DaprResponse):
    """The response of get_bulk_secret API.

    This inherits from DaprResponse

    Attributes:
        secret (Dict[str, Dict[str, str]]): secret received from response
    """

    def __init__(
            self,
            secrets: Dict[str, Dict[str, str]],
            headers: MetadataTuple = ()):
        """Initializes GetBulkSecretReponse from :obj:`dapr_v1.GetBulkSecretResponse`.

        Args:
            secrets (Dict[Str, Dict[str, str]]): the secret from Dapr response
            headers (Tuple, optional): the headers from Dapr gRPC response
        """
        super(GetBulkSecretResponse, self).__init__(headers)
        self._secrets = secrets

    @property
    def secrets(self) -> Dict[str, Dict[str, str]]:
        """Gets secrets as a dict."""
        return self._secrets


class StateResponse(DaprResponse):
    """The response of get_state API.

    This inherits from DaprResponse

    Attributes:
        data (bytes): the data in response from the get_state call
        etag (str): state's etag.
        headers (Tuple, optional): the headers from Dapr gRPC response
    """

    def __init__(
            self,
            data: Union[bytes, str],
            etag: str = '',
            headers: MetadataTuple = ()):
        """Initializes StateResponse from :obj:`runtime_v1.GetStateResponse`.

        Args:
            data (bytes): the data in response from the get_state call
            etag (str): state's etag.
            headers (Tuple, optional): the headers from Dapr gRPC response

        Raises:
            ValueError: if the response data is not :class:`google.protobuf.any_pb2.Any`
                object.
        """
        super(StateResponse, self).__init__(headers)
        self.data = data  # type: ignore
        self._etag = etag

    def text(self) -> str:
        """Gets content as str."""
        return to_str(self._data)

    def json(self) -> Dict[str, object]:
        """Gets content as deserialized JSON dictionary."""
        return json.loads(to_str(self._data))

    @property
    def etag(self) -> str:
        """Gets etag."""
        return self._etag

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

    def json(self) -> Dict[str, object]:
        """Gets content as deserialized JSON dictionary."""
        return json.loads(to_str(self._data))

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


class QueryResponseItem:
    """A query response item from state store query API.

    Attributes:
        key (str): query reponse item's key.
        value (bytes): query reponse item's data.
        etag (str): query reponse item's etag.
        error (str): error when state was retrieved
    """

    def __init__(
            self,
            key: str,
            value: bytes,
            etag: str = '',
            error: str = ''):
        """Initializes QueryResponseItem item from :obj:`runtime_v1.QueryStateItem`.

        Args:
            key (str): query response item's key.
            value (bytes): query response item's data.
            etag (str): query response item's etag.
            error (str): error when state was retrieved
        """
        self._key = key
        self._value = value
        self._etag = etag
        self._error = error

    def text(self) -> str:
        """Gets value as str."""
        return to_str(self._value)

    def json(self) -> Dict[str, object]:
        """Gets value as deserialized JSON dictionary."""
        return json.loads(to_str(self._value))

    @property
    def key(self) -> str:
        """Gets key."""
        return self._key

    @property
    def value(self) -> bytes:
        """Gets raw value."""
        return self._value

    @property
    def etag(self) -> str:
        """Gets etag."""
        return self._etag

    @property
    def error(self) -> str:
        """Gets error."""
        return self._error


class QueryResponse(DaprResponse):
    """The response of state store query API.

    This inherits from DaprResponse

    Attributes:
        results (Sequence[QueryResponseItem]): the query results.
        token (str): query response token for pagination.
        metadata (Dict[str, str]): query response metadata.
    """

    def __init__(
            self,
            results: Sequence[QueryResponseItem],
            token: str = '',
            metadata: Dict[str, str] = dict(),
            headers: MetadataTuple = ()):
        """Initializes QueryResponse from :obj:`runtime_v1.QueryStateResponse`.

        Args:
            results (Sequence[QueryResponseItem]): the query results.
            token (str): query response token for pagination.
            metadata (Dict[str, str]): query response metadata.
            headers (Tuple, optional): the headers from Dapr gRPC response.
        """
        super(QueryResponse, self).__init__(headers)
        self._metadata = metadata
        self._results = results
        self._token = token

    @property
    def results(self) -> Sequence[QueryResponseItem]:
        """Gets the query results."""
        return self._results

    @property
    def token(self) -> str:
        """Gets the query pagination token."""
        return self._token

    @property
    def metadata(self) -> Dict[str, str]:
        """Gets the query response metadata."""
        return self._metadata


class ConfigurationItem:
    """A config item from get_configuration API.

    Attributes:
        key (str): config's key.
        value (Union[bytes, str]): config's value.
        version (str): config's version.
        metadata (str): metadata
    """

    def __init__(
            self,
            key: str,
            value: str,
            version: str,
            metadata: Optional[Dict[str, str]] = dict()):
        """Initializes ConfigurationItem item from :obj:`runtime_v1.ConfigurationItem`.

        Args:
            key (str): config's key.
            value (str): config's value.
            version (str): config's version.
            metadata (Optional[Dict[str, str]] = dict()): metadata
        """
        self._key = key
        self._value = value
        self._version = version
        self._metadata = metadata

    def text(self) -> str:
        """Gets content as str."""
        return to_str(self._value)

    def json(self) -> Dict[str, object]:
        """Gets content as deserialized JSON dictionary."""
        return json.loads(to_str(self._value))

    @property
    def key(self) -> str:
        """Gets key."""
        return self._key

    @property
    def value(self) -> str:
        """Gets value."""
        return self._value

    @property
    def version(self) -> str:
        """Gets version."""
        return self._version

    @property
    def metadata(self) -> Optional[Dict[str, str]]:
        """Gets metadata."""
        return self._metadata


class ConfigurationResponse(DaprResponse):
    """The response of get_configuration API.

    This inherits from DaprResponse

    Attributes:
        data (Union[bytes, str]): state's data.
    """

    def __init__(
            self,
            items: Sequence[ConfigurationItem],
            headers: MetadataTuple = ()):
        """Initializes ConfigurationResponse from :obj:`runtime_v1.GetConfigurationResponse`.

        Args:
            items (Sequence[ConfigurationItem]): the items retrieved.
            headers (Tuple, optional): the headers from Dapr gRPC response.
        """
        super(ConfigurationResponse, self).__init__(headers)
        self._items = items

    @property
    def items(self) -> Sequence[ConfigurationItem]:
        """Gets the items."""
        return self._items
