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
    def __init__(
            self,
            headers: Optional[MetadataTuple] = (),
            trailers: Optional[MetadataTuple] = ()):
        self._headers = headers
        self._trailers = trailers

    def _from_tuple(self, metadata: Optional[MetadataTuple]) -> MetadataDict:
        d: MetadataDict = {}
        for k, v in metadata:  # type: ignore
            d.setdefault(k, []).append(v)
        return d

    @property
    def as_headers_dict(self) -> MetadataDict:
        return self._from_tuple(self._headers)

    @property
    def as_trailers_dict(self) -> MetadataDict:
        return self._from_tuple(self._trailers)


class InvokeServiceResponse(DaprResponse):
    def __init__(
            self,
            data: GrpcAny,
            content_type: Optional[str] = None,
            headers: Optional[MetadataTuple] = (),
            trailers: Optional[MetadataTuple] = ()):
        super(InvokeServiceResponse, self).__init__(headers, trailers)
        if not isinstance(data, GrpcMessage):
            raise ValueError('data is not protobuf message.')
        self._proto_any = data
        self._content_type = content_type

    @property
    def proto(self) -> GrpcAny:
        if not self.is_proto():
            raise ValueError('data is not grpc protobuf message')
        return self._proto_any

    @property
    def data(self) -> bytes:
        if self.is_proto():
            raise ValueError('data is not bytes')
        return self._proto_any.value

    @property
    def content_type(self) -> Optional[str]:
        return self._content_type

    def is_proto(self) -> bool:
        return self._proto_any.type_url != ''

    def unpack(self, message: GrpcMessage) -> None:
        if not self._proto_any.Is(message.DESCRIPTOR):
            raise ValueError(f'invalid type. serialized message type: {self._proto_any.type_url}')
        self._proto_any.Unpack(message)
