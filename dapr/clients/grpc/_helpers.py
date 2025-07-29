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
from typing import Dict, List, Union, Tuple, Optional, Any
from enum import Enum
from google.protobuf.any_pb2 import Any as GrpcAny
from google.protobuf.message import Message as GrpcMessage
from google.protobuf.wrappers_pb2 import (
    BoolValue,
    StringValue,
    Int32Value,
    Int64Value,
    DoubleValue,
    BytesValue,
)

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


def convert_parameter_value(value: Any) -> GrpcAny:
    """Convert a raw Python value to a GrpcAny protobuf message.

    This function automatically detects the type of the input value and wraps it
    in the appropriate protobuf wrapper type before packing it into GrpcAny.

    Args:
        value: Raw Python value (str, int, float, bool, bytes, or already GrpcAny)

    Returns:
        GrpcAny: The value wrapped in a GrpcAny protobuf message

    Raises:
        ValueError: If the value type is not supported

    Examples:
        >>> convert_parameter_value("hello")  # -> GrpcAny containing StringValue
        >>> convert_parameter_value(42)       # -> GrpcAny containing Int64Value
        >>> convert_parameter_value(3.14)     # -> GrpcAny containing DoubleValue
        >>> convert_parameter_value(True)     # -> GrpcAny containing BoolValue
    """
    # If it's already a GrpcAny, return as-is (backward compatibility)
    if isinstance(value, GrpcAny):
        return value

    # Create the GrpcAny wrapper
    any_pb = GrpcAny()

    # Convert based on Python type
    if isinstance(value, bool):
        # Note: bool check must come before int since bool is a subclass of int in Python
        any_pb.Pack(BoolValue(value=value))
    elif isinstance(value, str):
        any_pb.Pack(StringValue(value=value))
    elif isinstance(value, int):
        # Use Int64Value to handle larger integers, but Int32Value for smaller ones
        if -2147483648 <= value <= 2147483647:
            any_pb.Pack(Int32Value(value=value))
        else:
            any_pb.Pack(Int64Value(value=value))
    elif isinstance(value, float):
        any_pb.Pack(DoubleValue(value=value))
    elif isinstance(value, bytes):
        any_pb.Pack(BytesValue(value=value))
    else:
        raise ValueError(f"Unsupported parameter type: {type(value)}. "
                        f"Supported types: str, int, float, bool, bytes, GrpcAny")

    return any_pb


def convert_parameters(parameters: Optional[Dict[str, Any]]) -> Dict[str, GrpcAny]:
    """Convert a dictionary of raw Python values to GrpcAny parameters.

    This function takes a dictionary with raw Python values and converts each
    value to the appropriate GrpcAny protobuf message for use in Dapr API calls.

    Args:
        parameters: Optional dictionary of parameter names to raw Python values

    Returns:
        Dictionary of parameter names to GrpcAny values

    Examples:
        >>> convert_parameters({"temperature": 0.7, "max_tokens": 1000, "stream": False})
        >>> # Returns: {"temperature": GrpcAny, "max_tokens": GrpcAny, "stream": GrpcAny}
    """
    if not parameters:
        return {}

    converted = {}
    for key, value in parameters.items():
        converted[key] = convert_parameter_value(value)

    return converted
