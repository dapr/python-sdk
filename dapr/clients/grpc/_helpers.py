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
from enum import Enum
from typing import Any, Dict, List, Optional, Union, Tuple


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
from google.protobuf.struct_pb2 import Struct
from google.protobuf import json_format

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


def convert_value_to_struct(value: Dict[str, Any]) -> Struct:
    """Convert a raw Python value to a protobuf Struct message.

    This function converts Python values to a protobuf Struct, which is designed
    to represent JSON-like dynamic data structures.

    Args:
        value: Raw Python value (str, int, float, bool, None, dict, list, or already Struct)

    Returns:
        Struct: The value converted to a protobuf Struct message

    Raises:
        ValueError: If the value type is not supported or cannot be serialized

    Examples:
        >>> convert_value_to_struct("hello")  # -> Struct with string value
        >>> convert_value_to_struct(42)       # -> Struct with number value
        >>> convert_value_to_struct(True)     # -> Struct with bool value
        >>> convert_value_to_struct({"key": "value"})  # -> Struct with nested structure
    """
    # If it's already a Struct, return as-is (backward compatibility)
    if isinstance(value, Struct):
        return value

    # raise an error if the value is not a dictionary
    if not isinstance(value, dict) and not isinstance(value, bytes):
        raise ValueError(f'Value must be a dictionary, got {type(value)}')

    # Convert the value to a JSON-serializable format first
    # Handle bytes by converting to base64 string for JSON compatibility
    if isinstance(value, bytes):
        import base64

        json_value = base64.b64encode(value).decode('utf-8')
    else:
        json_value = value

    try:
        # For dict values, use ParseDict directly
        struct = Struct()
        json_format.ParseDict(json_value, struct)
        return struct

    except (TypeError, ValueError) as e:
        raise ValueError(
            f'Unsupported parameter type or value: {type(value)} = {repr(value)}. '
            f'Must be JSON-serializable. Error: {e}'
        ) from e


def convert_value_to_grpc_any(value: Any) -> GrpcAny:
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
        >>> convert_value_to_grpc_any("hello")  # -> GrpcAny containing StringValue
        >>> convert_value_to_grpc_any(42)       # -> GrpcAny containing Int64Value
        >>> convert_value_to_grpc_any(3.14)     # -> GrpcAny containing DoubleValue
        >>> convert_value_to_grpc_any(True)     # -> GrpcAny containing BoolValue
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
        raise ValueError(
            f'Unsupported parameter type: {type(value)}. '
            f'Supported types: str, int, float, bool, bytes, GrpcAny'
        )

    return any_pb


def convert_dict_to_grpc_dict_of_any(parameters: Optional[Dict[str, Any]]) -> Dict[str, GrpcAny]:
    """Convert a dictionary of raw Python values to GrpcAny parameters.
    This function takes a dictionary with raw Python values and converts each
    value to the appropriate GrpcAny protobuf message for use in Dapr API calls.
    Args:
        parameters: Optional dictionary of parameter names to raw Python values
    Returns:
        Dictionary of parameter names to GrpcAny values
    Examples:
        >>> convert_dict_to_grpc_dict_of_any({"temperature": 0.7, "max_tokens": 1000, "stream": False})
        >>> # Returns: {"temperature": GrpcAny, "max_tokens": GrpcAny, "stream": GrpcAny}
    """
    if not parameters:
        return {}

    converted = {}
    for key, value in parameters.items():
        converted[key] = convert_value_to_grpc_any(value)

    return converted
