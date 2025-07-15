
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
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple, Union

from google.protobuf.any_pb2 import Any as GrpcAny
from google.protobuf.message import Message as GrpcMessage
from google.protobuf.wrappers_pb2 import (
    BoolValue,
    DoubleValue,
    Int32Value,
    Int64Value,
    StringValue,
)

MetadataDict = Dict[str, List[Union[bytes, str]]]
MetadataTuple = Tuple[Tuple[str, Union[bytes, str]], ...]


def convert_parameters_for_grpc(params: Optional[Dict[str, Any]]) -> Dict[str, GrpcAny]:
    """
    Convert raw Python values to protobuf Any objects for conversation API.

    This function improves developer experience by automatically converting
    common Python types to the protobuf Any format required by the gRPC API.

    Args:
        params: Dictionary of parameters with raw Python values or pre-wrapped
                protobuf Any objects

    Returns:
        Dictionary with values converted to protobuf Any objects

    Examples:
        >>> params = {"tool_choice": "auto", "temperature": 0.7, "max_tokens": 1000}
        >>> converted = convert_parameters_for_grpc(params)
        >>> # Returns protobuf Any objects that can be sent via gRPC
    """
    if not params:
        return {}

    converted = {}

    for key, value in params.items():
        # Skip if already a protobuf Any (backward compatibility)
        if isinstance(value, GrpcAny):
            converted[key] = value
            continue

        # Convert based on type
        any_value = GrpcAny()

        if isinstance(value, str):
            any_value.Pack(StringValue(value=value))
        elif isinstance(value, bool):  # Check bool before int (bool is subclass of int)
            any_value.Pack(BoolValue(value=value))
        elif isinstance(value, int):
            # Choose appropriate int wrapper based on value range
            if -2147483648 <= value <= 2147483647:
                any_value.Pack(Int32Value(value=value))
            else:
                any_value.Pack(Int64Value(value=value))
        elif isinstance(value, float):
            # Use DoubleValue for better precision
            any_value.Pack(DoubleValue(value=value))
        else:
            # For unsupported types, convert to string as fallback
            any_value.Pack(StringValue(value=str(value)))

        converted[key] = any_value

    return converted


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
