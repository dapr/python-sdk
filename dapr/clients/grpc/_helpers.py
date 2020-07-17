# -*- coding: utf-8 -*-

"""
Copyright (c) Microsoft Corporation.
Licensed under the MIT License.
"""

from typing import Dict, List, Union, Tuple
from google.protobuf.any_pb2 import Any as GrpcAny
from google.protobuf.message import Message as GrpcMessage

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
