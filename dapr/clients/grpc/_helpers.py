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
from typing import Dict, List, Union, Tuple, Optional
from enum import Enum
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


def to_bytes(data: Union[str, bytes]) -> bytes:
    """Convert str data to bytes."""
    if isinstance(data, bytes):
        return data
    elif isinstance(data, str):
        return data.encode('utf-8')
    else:
        raise f'invalid data type {type(data)}'


def to_str(data: Union[str, bytes]) -> str:
    """Convert bytes data to str."""
    if isinstance(data, str):
        return data
    elif isinstance(data, bytes):
        return data.decode('utf-8')
    else:
        raise f'invalid data type {type(data)}'


# Data validation helpers
def validateNotNone(**kwargs: Optional[str]):
    for field_name, value in kwargs.items():
        if value is None:
            raise ValueError(f'{field_name} name cannot be None')


def validateNotBlankString(**kwargs: Optional[str]):
    for field_name, value in kwargs.items():
        if not value or not value.strip():
            raise ValueError(f'{field_name} name cannot be empty or blank')


class WorkflowRuntimeStatus(Enum):
    UNKNOWN = 'Unknown'
    RUNNING = 'Running'
    COMPLETED = 'Completed'
    FAILED = 'Failed'
    TERMINATED = 'Terminated'
    PENDING = 'Pending'
    SUSPENDED = 'Suspended'


# Will return the enum entry if it is present, otherwise returns "unknown"
def getWorkflowRuntimeStatus(inputString):
    try:
        return WorkflowRuntimeStatus[inputString].value
    except KeyError:
        return WorkflowRuntimeStatus.UNKNOWN
