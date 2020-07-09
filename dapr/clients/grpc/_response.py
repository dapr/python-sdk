# -*- coding: utf-8 -*-

"""
Copyright (c) Microsoft Corporation.
Licensed under the MIT License.
"""

from typing import Optional

from google.protobuf.any_pb2 import Any as GrpcAny
from google.protobuf.message import Message as GrpcMessage

from dapr.clients.grpc._helpers import MetadataDict, MetadataTuple


class DaprResponse:
    """A base class for Dapr Response.

    This is the base class for Dapr Response. User can gets the headers and trailers as
    a dict.

    Attributes:
        headers(dict): A dict to include the headers from Dapr gRPC Response.
        trailers(dict): A dict to include the trailers from Dapr gRPC Response.
    """

    def __init__(
            self,
            headers: Optional[MetadataTuple] = (),
            trailers: Optional[MetadataTuple] = ()):
        """Inits DapResponse with headers and trailers.

        Args:
            headers (Tuple, optional): the tuple for the headers from gRPC response
            trailers (Tuple, optional): the tuple for the trailers from gRPC response
        """
        self._headers = self._from_tuple(headers)
        self._trailers = self._from_tuple(trailers)

    def _from_tuple(self, metadata: Optional[MetadataTuple]) -> MetadataDict:
        d: MetadataDict = {}
        for k, v in metadata:  # type: ignore
            d.setdefault(k, []).append(v)
        return d

    @property
    def headers(self) -> MetadataDict:
        """Returns headers tuple as a dict."""
        return self._headers

    @property
    def trailers(self) -> MetadataDict:
        """Returns trailers tuple as a dict."""
        return self._trailers


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
            data: GrpcAny,
            content_type: Optional[str] = None,
            headers: Optional[MetadataTuple] = (),
            trailers: Optional[MetadataTuple] = ()):
        """Initializes InvokeServiceReponse from :obj:`common_v1.InvokeResponse`.

        Args:
            data (:obj:`google.protobuf.any_pb2.Any`): the response data from Dapr response
            content_type (str, optional): the content type of the bytes data
            headers (Tuple, optional): the headers from Dapr gRPC response
            trailers (Tuple, optional): the trailers from Dapr gRPC response

        Raises:
            ValueError: if the response data is not :class:`google.protobuf.any_pb2.Any`
                object.
        """
        super(InvokeServiceResponse, self).__init__(headers, trailers)
        if not isinstance(data, GrpcAny):
            raise ValueError('data is not protobuf message.')
        self._proto_any = data
        self._content_type = content_type

    @property
    def data(self) -> GrpcAny:
        """Gets raw serialized protocol buffer message.

        Raises:
            ValueError: data is not protocol buffer message object
        """
        if not self.is_proto():
            raise ValueError('data is not protocol buffer message object')
        return self._proto_any

    @property
    def content(self) -> bytes:
        """Gets raw bytes data if the response data content is not serialized
        protocol buffer message.

        Raises:
            ValueError: the response data is the serialized protocol buffer message
        """
        if self.is_proto():
            raise ValueError('data is the serialized protocol buffer message')
        return self._proto_any.value

    def text(self) -> str:
        """Gets content as str if the response data content is not serialized
        protocol buffer message.

        Raises:
            ValueError: the response data is the serialized protocol buffer message
        """
        return self.content.decode('utf-8')

    @property
    def content_type(self) -> Optional[str]:
        """Gets the content type of content attribute."""
        return self._content_type

    def is_proto(self) -> bool:
        """Returns True if the response data is the serialized protocol buffer message."""
        return self._proto_any.type_url != ''

    def unpack(self, message: GrpcMessage) -> None:
        """Unpack the serialized protocol buffer message.

        Args:
            message (:obj:`google.protobuf.message.Message`): the protocol buffer message object
                to which the response data is deserialized.

        Raises:
            ValueError: message is not protocol buffer message object or message's type is not
                matched with the response data type
        """
        if not isinstance(message, GrpcMessage):
            raise ValueError('output message is not protocol buffer message object')
        if not self._proto_any.Is(message.DESCRIPTOR):
            raise ValueError(f'invalid type. serialized message type: {self._proto_any.type_url}')
        self._proto_any.Unpack(message)
