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

import io
from enum import Enum
from typing import Dict, Optional, Union

from google.protobuf.any_pb2 import Any as GrpcAny
from google.protobuf.message import Message as GrpcMessage
from dapr.proto import api_v1, common_v1

from dapr.clients.base import DEFAULT_JSON_CONTENT_TYPE
from dapr.clients.grpc._crypto import EncryptOptions, DecryptOptions
from dapr.clients.grpc._helpers import (
    MetadataDict,
    MetadataTuple,
    tuple_to_dict,
    to_bytes,
    to_str,
    unpack,
)


class DaprRequest:
    """A base class for Dapr Request.

    This is the base class for Dapr Request. User can get the metadata.

    Attributes:
        metadata(dict): A dict to include the headers from Dapr Request.
    """

    def __init__(self, metadata: MetadataTuple = ()):
        self.metadata = metadata  # type: ignore

    @property
    def metadata(self) -> MetadataDict:
        """Get metadata from :class:`DaprRequest`."""
        return self.get_metadata(as_dict=True)  # type: ignore

    @metadata.setter
    def metadata(self, val) -> None:
        """Sets metadata."""
        if not isinstance(val, tuple):
            raise ValueError('val is not tuple')
        self._metadata = val

    def get_metadata(self, as_dict: bool = False) -> Union[MetadataDict, MetadataTuple]:
        """Gets metadata from the request.

        Args:
            as_dict (bool): dict type metadata if as_dict is True. Otherwise, return
                tuple metadata.

        Returns:
            dict or tuple: request metadata.
        """
        if as_dict:
            return tuple_to_dict(self._metadata)
        return self._metadata


class InvokeMethodRequest(DaprRequest):
    """A request data representation for invoke_method API.

    This stores the request data with the proper serialization. This seralizes
    data to :obj:`google.protobuf.any_pb2.Any` if data is the type of protocol
    buffer message.

    Attributes:
        metadata(dict): A dict to include the headers from Dapr Request.
        data (str, bytes, GrpcAny, GrpcMessage, optional): the serialized data
            for invoke_method request.
        content_type (str, optional): the content type of data which is valid
            only for bytes array data.
    """

    HTTP_METHODS = ['GET', 'HEAD', 'POST', 'PUT', 'DELETE', 'CONNECT', 'OPTIONS', 'TRACE']

    def __init__(
        self,
        data: Union[str, bytes, GrpcAny, GrpcMessage, None] = None,
        content_type: Optional[str] = None,
    ):
        """Inits InvokeMethodRequestData with data and content_type.

        Args:
            data (bytes, str, GrpcAny, GrpcMessage, optional): the data
                which is used for invoke_method request.
            content_type (str): the content_type of data when the data is bytes.
                The default content type is application/json.

        Raises:
            ValueError: data is not supported.
        """
        super(InvokeMethodRequest, self).__init__(())

        self._content_type = content_type
        self._http_verb = None
        self._http_querystring: Dict[str, str] = {}

        self.set_data(data)

        # Set content_type to application/json type if content_type
        # is not given and date is bytes or str type.
        if not self.is_proto() and not content_type:
            self.content_type = DEFAULT_JSON_CONTENT_TYPE

    @property
    def http_verb(self) -> Optional[str]:
        """Gets HTTP method in Dapr invocation request."""
        return self._http_verb

    @http_verb.setter
    def http_verb(self, val: Optional[str]) -> None:
        """Sets HTTP method to Dapr invocation request."""
        if val not in self.HTTP_METHODS:
            raise ValueError(f'{val} is the invalid HTTP verb.')
        self._http_verb = val

    @property
    def http_querystring(self) -> Dict[str, str]:
        """Gets HTTP querystring as dict."""
        return self._http_querystring

    def is_http(self) -> bool:
        """Return true if this request is http compatible."""
        return hasattr(self, '_http_verb') and not (not self._http_verb)

    @property
    def proto(self) -> GrpcAny:
        """Gets raw data as proto any type."""
        return self._data

    def is_proto(self) -> bool:
        """Returns true if data is protocol-buffer serialized."""
        return hasattr(self, '_data') and self._data.type_url != ''

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
            message (:obj:`GrpcMessage`): the protocol buffer message object
                to which the response data is deserialized.

        Raises:
            ValueError: message is not protocol buffer message object or message's type is not
                matched with the response data type
        """
        unpack(self.proto, message)

    @property
    def data(self) -> bytes:
        """Gets request data as bytes."""
        if self.is_proto():
            raise ValueError('data is protocol buffer message object.')
        return self._data.value

    @data.setter
    def data(self, val: Union[str, bytes]) -> None:
        """Sets str or bytes type data to request data."""
        self.set_data(to_bytes(val))

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
        """Gets the request data as str."""
        return to_str(self.data)

    @property
    def content_type(self) -> Optional[str]:
        """Gets content_type for bytes data."""
        return self._content_type

    @content_type.setter
    def content_type(self, val: Optional[str]) -> None:
        """Sets content type for bytes data."""
        self._content_type = val


class BindingRequest(DaprRequest):
    """A request data representation for invoke_binding API.

    This stores the request data and metadata with the proper serialization.
    This seralizes data to bytes and metadata to a dictionary of key value pairs.

    Attributes:
        data (bytes): the data which is used for invoke_binding request.
        metadata (Dict[str, str]): the metadata sent to the binding.
    """

    def __init__(self, data: Union[str, bytes], binding_metadata: Dict[str, str] = {}):
        """Inits BindingRequest with data and metadata if given.

        Args:
            data (bytes, str): the data which is used for invoke_binding request.
            binding_metadata (tuple, optional): the metadata to be sent to the binding.

        Raises:
            ValueError: data is not bytes or str.
        """
        super(BindingRequest, self).__init__(())
        self.data = data  # type: ignore
        self._binding_metadata = binding_metadata

    @property
    def data(self) -> bytes:
        """Gets request data as bytes."""
        return self._data

    @data.setter
    def data(self, val: Union[str, bytes]) -> None:
        """Sets str or bytes type data to request data."""
        self._data = to_bytes(val)

    def text(self) -> str:
        """Gets the request data as str."""
        return to_str(self.data)

    @property
    def binding_metadata(self):
        """Gets the metadata for output binding."""
        return self._binding_metadata


class TransactionOperationType(Enum):
    """Represents the type of operation for a Dapr Transaction State Api Call"""

    upsert = 'upsert'
    delete = 'delete'


class TransactionalStateOperation:
    """An upsert or delete operation for a state transaction, 'upsert' by default.

    Attributes:
        key (str): state's key.
        data (Union[bytes, str]): state's data.
        etag (str): state's etag.
        operation_type (TransactionOperationType): operation to be performed.
    """

    def __init__(
        self,
        key: str,
        data: Optional[Union[bytes, str]] = None,
        etag: Optional[str] = None,
        operation_type: TransactionOperationType = TransactionOperationType.upsert,
    ):
        """Initializes TransactionalStateOperation item from
        :obj:`runtime_v1.TransactionalStateOperation`.

        Args:
            key (str): state's key.
            data (Union[bytes, str]): state's data.
            etag (str): state's etag.
            operationType (Optional[TransactionOperationType]): operation to be performed.

        Raises:
            ValueError: data is not bytes or str.
        """
        if operation_type != TransactionOperationType.delete and not isinstance(data, (bytes, str)):
            raise ValueError(f'invalid type for data {type(data)}')

        self._key = key
        self._data = data  # type: ignore
        self._etag = etag
        self._operation_type = operation_type

    @property
    def key(self) -> str:
        """Gets key."""
        return self._key

    @property
    def data(self) -> Union[bytes, str, None]:
        """Gets raw data."""
        return self._data

    @property
    def etag(self) -> Optional[str]:
        """Gets etag."""
        return self._etag

    @property
    def operation_type(self) -> TransactionOperationType:
        """Gets etag."""
        return self._operation_type


class EncryptRequestIterator(DaprRequest):
    """An iterator for cryptography encrypt API requests.

    This reads data from a given stream by chunks and converts it to an iterator of
    cryptography encrypt API requests.
    This iterator will be used for encrypt gRPC bidirectional streaming requests.
    """

    def __init__(
        self,
        data: Union[str, bytes],
        options: EncryptOptions,
    ):
        """Initialize EncryptRequestIterator with data and encryption options.

        Args:
            data (Union[str, bytes]): data to be encrypted
            options (EncryptOptions): encryption options
        """
        self.data = io.BytesIO(to_bytes(data))
        self.options = options.get_proto()
        self.buffer_size = 2 << 10  # 2KiB
        self.seq = 0

    def __iter__(self):
        """Returns the iterator object itself."""
        return self

    def __next__(self):
        """Read the next chunk of data from the input stream and create a gRPC stream request."""
        # Read data from the input stream, in chunks of up to 2KiB
        # Send the data until we reach the end of the input stream
        chunk = self.data.read(self.buffer_size)
        if not chunk:
            raise StopIteration

        payload = common_v1.StreamPayload(data=chunk, seq=self.seq)
        if self.seq == 0:
            # If this is the first chunk, add the options
            request_proto = api_v1.EncryptRequest(payload=payload, options=self.options)
        else:
            request_proto = api_v1.EncryptRequest(payload=payload)

        self.seq += 1
        return request_proto


class DecryptRequestIterator(DaprRequest):
    """An iterator for cryptography decrypt API requests.

    This reads data from a given stream by chunks and converts it to an iterator of decrypt
    cryptography API requests.
    This iterator will be used for decrypt gRPC bidirectional streaming requests.
    """

    def __init__(
        self,
        data: Union[str, bytes],
        options: DecryptOptions,
    ):
        """Initialize DecryptRequestIterator with data and decryption options.

        Args:
            data (Union[str, bytes]): data to be decrypted
            options (DecryptOptions): decryption options
        """
        self.data = io.BytesIO(to_bytes(data))
        self.options = options.get_proto()
        self.buffer_size = 2 << 10  # 2KiB
        self.seq = 0

    def __iter__(self):
        """Returns the iterator object itself."""
        return self

    def __next__(self):
        """Read the next chunk of data from the input stream and create a gRPC stream request."""
        # Read data from the input stream, in chunks of up to 2KiB
        # Send the data until we reach the end of the input stream
        chunk = self.data.read(self.buffer_size)
        if not chunk:
            raise StopIteration

        payload = common_v1.StreamPayload(data=chunk, seq=self.seq)
        if self.seq == 0:
            # If this is the first chunk, add the options
            request_proto = api_v1.DecryptRequest(payload=payload, options=self.options)
        else:
            request_proto = api_v1.DecryptRequest(payload=payload)

        self.seq += 1
        return request_proto
