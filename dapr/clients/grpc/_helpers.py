# -*- coding: utf-8 -*-

"""
Copyright (c) Microsoft Corporation.
Licensed under the MIT License.
"""

from collections import namedtuple
from typing import Dict, List, Union, Tuple

from google.protobuf.any_pb2 import Any as GrpcAny
from google.protobuf.message import Message as GrpcMessage
from grpc import UnaryUnaryClientInterceptor, ClientCallDetails     # type: ignore

MetadataDict = Dict[str, List[Union[bytes, str]]]
MetadataTuple = Tuple[Tuple[str, Union[bytes, str]], ...]


def tuple_to_dict(tupledata: MetadataTuple) -> MetadataDict:
    """Converts tuple to dict.

    Args:
        tupledata (tuple): tuple storing metadata

    Returns:
        A dict which is converted from tuple
    """

    d: MetadataDict = {}
    for k, v in tupledata:  # type: ignore
        d.setdefault(k, []).append(v)
    return d


def unpack(data: GrpcAny, message: GrpcMessage) -> None:
    """Unpack the serialized protocol buffer message.

    Args:
        data (:obj:`google.protobuf.message.Any`): the serialized protocol buffer message.
        message (:obj:`google.protobuf.message.Message`): the protocol buffer message object
            to which the response data is deserialized.

    Raises:
        ValueError: message is not protocol buffer message object or message's type is not
            matched with the response data type
    """
    if not isinstance(message, GrpcMessage):
        raise ValueError('output message is not protocol buffer message object')
    if not data.Is(message.DESCRIPTOR):
        raise ValueError(f'invalid type. serialized message type: {data.type_url}')
    data.Unpack(message)


def to_bytes(data: Union[str, bytes]) -> bytes:
    """Convert str data to bytes."""
    if isinstance(data, bytes):
        return data
    elif isinstance(data, str):
        return data.encode('utf-8')
    else:
        raise(f'invalid data type {type(data)}')


def to_str(data: Union[str, bytes]) -> str:
    """Convert bytes data to str."""
    if isinstance(data, str):
        return data
    elif isinstance(data, bytes):
        return data.decode('utf-8')
    else:
        raise(f'invalid data type {type(data)}')


class _ClientCallDetails(
        namedtuple(
            '_ClientCallDetails',
            ['method', 'timeout', 'metadata', 'credentials', 'wait_for_ready', 'compression']),
        ClientCallDetails):
    """This is an implementation of the ClientCallDetails interface needed for interceptors.
    This class takes six named values and inherits the ClientCallDetails from grpc package.
    This class encloses the values that describe a RPC to be invoked.
    """
    pass


class DaprClientInterceptor(UnaryUnaryClientInterceptor):
    """The class implements a UnaryUnaryClientInterceptor from grpc to add an interceptor to add
    additional headers to all calls as needed.

    Examples:

        interceptor = HeaderInterceptor([('header', 'value', )])
        intercepted_channel = grpc.intercept_channel(grpc_channel, interceptor)

    With multiple header values:

        interceptor = HeaderInterceptor([('header1', 'value1', ), ('header2', 'value2', )])
        intercepted_channel = grpc.intercept_channel(grpc_channel, interceptor)
    """

    def __init__(
            self,
            metadata: List[Tuple[str, str]]):
        """Initializes the metadata field for the class.

        Args:
            metadata list[tuple[str, str]]: list of tuple of (key, value) strings
            representing header values
        """

        self._metadata = metadata

    def _intercept_call(
            self,
            client_call_details: ClientCallDetails) -> ClientCallDetails:
        """Internal intercept_call implementation which adds metadata to grpc metadata in the RPC
        call details.

        Args:
            client_call_details :class: `ClientCallDetails`: object that describes a RPC
            to be invoked

        Returns:
            :class: `ClientCallDetails` modified call details
        """

        metadata = []
        if client_call_details.metadata is not None:
            metadata = list(client_call_details.metadata)
        metadata.extend(self._metadata)

        new_call_details = _ClientCallDetails(
            client_call_details.method, client_call_details.timeout, metadata,
            client_call_details.credentials, client_call_details.wait_for_ready,
            client_call_details.compression)
        return new_call_details

    def intercept_unary_unary(
            self,
            continuation,
            client_call_details,
            request):
        """This method intercepts a unary-unary gRPC call. This is the implementation of the
        abstract method defined in UnaryUnaryClientInterceptor defined in grpc. This is invoked
        automatically by grpc based on the order in which interceptors are added to the channel.

        Args:
            continuation: a callable to be invoked to continue with the RPC or next interceptor
            client_call_details: a ClientCallDetails object describing the outgoing RPC
            request: the request value for the RPC

        Returns:
            A response object after invoking the continuation callable
        """

        # Pre-process or intercept call
        new_call_details = self._intercept_call(client_call_details)
        # Call continuation
        response = continuation(new_call_details, request)
        return response
