# -*- coding: utf-8 -*-

"""
Copyright 2025 The Dapr Authors
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


import inspect
from dataclasses import fields, is_dataclass
from enum import Enum
from typing import Any, Dict, Optional, Union, get_args, get_origin, get_type_hints

"""
Schema Helpers for Dapr Conversation API.

This module provides function-to-JSON-schema helpers that automatically
convert typed Python functions to tools for the Conversation API.
"""


def python_type_to_json_schema(python_type: Any, field_name: str = '') -> Dict[str, Any]:
    """Convert a Python type hint to JSON schema format.

    Args:
        python_type: The Python type to convert
        field_name: The name of the field (for better error messages)

    Returns:
        Dict representing the JSON schema for this type

    Examples:
        >>> python_type_to_json_schema(str)
        {"type": "string"}
        >>> python_type_to_json_schema(Optional[int])
        {"type": "integer"}
        >>> python_type_to_json_schema(List[str])
        {"type": "array", "items": {"type": "string"}}
    """
    # Handle None type
    if python_type is type(None):
        return {'type': 'null'}

    # Get the origin type for generic types (List, Dict, Union, etc.)
    origin = get_origin(python_type)
    args = get_args(python_type)

    # Handle Union types (including Optional which is Union[T, None])
    if origin is Union:
        # Check if this is Optional[T] (Union[T, None])
        non_none_args = [arg for arg in args if arg is not type(None)]
        if len(non_none_args) == 1 and type(None) in args:
            # This is Optional[T], convert T
            return python_type_to_json_schema(non_none_args[0], field_name)
        else:
            # This is a true Union, use anyOf
            return {'anyOf': [python_type_to_json_schema(arg, field_name) for arg in args]}

    # Handle List types
    if origin is list or python_type is list:
        if args:
            return {
                'type': 'array',
                'items': python_type_to_json_schema(args[0], f'{field_name}[]'),
            }
        else:
            return {'type': 'array'}

    # Handle Dict types
    if origin is dict or python_type is dict:
        schema = {'type': 'object'}
        if args and len(args) == 2:
            # Dict[str, ValueType] - add additionalProperties
            key_type, value_type = args
            if key_type is str:
                schema['additionalProperties'] = python_type_to_json_schema(
                    value_type, f'{field_name}.*'
                )
        return schema

    # Handle basic types
    if python_type is str:
        return {'type': 'string'}
    elif python_type is int:
        return {'type': 'integer'}
    elif python_type is float:
        return {'type': 'number'}
    elif python_type is bool:
        return {'type': 'boolean'}
    elif python_type is bytes:
        return {'type': 'string', 'format': 'byte'}

    # Handle Enum types
    if inspect.isclass(python_type) and issubclass(python_type, Enum):
        return {'type': 'string', 'enum': [item.value for item in python_type]}

    # Handle Pydantic models (if available)
    if hasattr(python_type, 'model_json_schema'):
        try:
            return python_type.model_json_schema()
        except Exception:
            pass
    elif hasattr(python_type, 'schema'):
        try:
            return python_type.schema()
        except Exception:
            pass

    # Handle dataclasses
    if is_dataclass(python_type):
        from dataclasses import MISSING

        schema = {'type': 'object', 'properties': {}, 'required': []}

        for field in fields(python_type):
            field_schema = python_type_to_json_schema(field.type, field.name)
            schema['properties'][field.name] = field_schema

            # Check if field has no default (required) - use MISSING for dataclasses
            if field.default is MISSING:
                schema['required'].append(field.name)

        return schema

    # Fallback for unknown types
    return {'type': 'string', 'description': f'Unknown type: {python_type}'}


def extract_docstring_info(func) -> Dict[str, str]:
    """Extract parameter descriptions from function docstring.

    Supports Google-style, NumPy-style, and Sphinx-style docstrings.

    Args:
        func: The function to analyze

    Returns:
        Dict mapping parameter names to their descriptions
    """
    docstring = inspect.getdoc(func)
    if not docstring:
        return {}

    param_descriptions = {}

    # Simple regex-based extraction for common docstring formats
    lines = docstring.split('\n')
    in_args_section = False
    current_param = None

    for line in lines:
        line = line.strip()

        # Detect Args/Parameters section
        if line.lower() in ('args:', 'arguments:', 'parameters:', 'params:'):
            in_args_section = True
            continue

        # Exit args section on new section
        if in_args_section and line.endswith(':') and not line.startswith(' '):
            in_args_section = False
            continue

        if in_args_section and line:
            # Look for parameter definitions (contains colon and doesn't look like a continuation)
            if ':' in line and not line.startswith(' '):
                parts = line.split(':', 1)
                if len(parts) == 2:
                    param_name = parts[0].strip()
                    description = parts[1].strip()
                    # Handle type annotations like "param_name (type): description"
                    if '(' in param_name and ')' in param_name:
                        param_name = param_name.split('(')[0].strip()
                    param_descriptions[param_name] = description
                    current_param = param_name
            elif current_param:
                # Continuation of previous parameter description
                param_descriptions[current_param] += ' ' + line.strip()

    return param_descriptions


def function_to_json_schema(
    func, name: Optional[str] = None, description: Optional[str] = None
) -> Dict[str, Any]:
    """Convert a Python function to a JSON schema for tool calling.

    Args:
        func: The Python function to convert
        name: Override the function name (defaults to func.__name__)
        description: Override the function description (defaults to first line of docstring)

    Returns:
        Complete JSON schema with properties and required fields

    Examples:
        >>> def get_weather(location: str, unit: str = "fahrenheit") -> str:
        ...     '''Get weather for a location.
        ...
        ...     Args:
        ...         location: The city name
        ...         unit: Temperature unit (celsius or fahrenheit)
        ...     '''
        ...     pass
        >>> schema = function_to_json_schema(get_weather)
        >>> schema["properties"]["location"]["type"]
        'string'
    """
    # Get function signature and type hints
    sig = inspect.signature(func)
    type_hints = get_type_hints(func)

    # Extract parameter descriptions from docstring
    param_descriptions = extract_docstring_info(func)

    # Get function description
    if description is None:
        docstring = inspect.getdoc(func)
        if docstring:
            # Use first line of docstring as description
            description = docstring.split('\n')[0].strip()
        else:
            description = f'Function {func.__name__}'

    # Build JSON schema
    schema = {'type': 'object', 'properties': {}, 'required': []}

    for param_name, param in sig.parameters.items():
        # Skip *args and **kwargs
        if param.kind in (param.VAR_POSITIONAL, param.VAR_KEYWORD):
            continue

        # Get type hint
        param_type = type_hints.get(param_name, str)

        # Convert to JSON schema
        param_schema = python_type_to_json_schema(param_type, param_name)

        # Add description if available
        if param_name in param_descriptions:
            param_schema['description'] = param_descriptions[param_name]

        schema['properties'][param_name] = param_schema

        # Check if parameter is required (no default value)
        if param.default is param.empty:
            schema['required'].append(param_name)

    return schema


def create_tool_from_function(func, name: Optional[str] = None, description: Optional[str] = None):
    """Create a ConversationTools from a Python function with type hints.

    This provides the ultimate developer experience - just define a typed function
    and automatically get a properly configured tool for the Conversation API.

    Args:
        func: Python function with type hints
        name: Override function name (defaults to func.__name__)
        description: Override description (defaults to docstring)

    Returns:
        ConversationTools ready to use with Alpha2 API

    Examples:
        >>> def get_weather(location: str, unit: str = "fahrenheit") -> str:
        ...     '''Get current weather for a location.
        ...
        ...     Args:
        ...         location: The city and state or country
        ...         unit: Temperature unit preference
        ...     '''
        ...     return f"Weather in {location}: sunny, 72°F"

        >>> weather_tool = create_tool_from_function(get_weather)
        # Now use weather_tool in your conversation API calls!

        >>> # With Pydantic models
        >>> from pydantic import BaseModel
        >>> class SearchQuery(BaseModel):
        ...     query: str
        ...     limit: int = 10
        ...     include_images: bool = False

        >>> def web_search(params: SearchQuery) -> str:
        ...     '''Search the web for information.'''
        ...     return f"Search results for: {params.query}"

        >>> search_tool = create_tool_from_function(web_search)

        >>> # With Enums
        >>> from enum import Enum
        >>> class Units(Enum):
        ...     CELSIUS = "celsius"
        ...     FAHRENHEIT = "fahrenheit"

        >>> def get_temperature(city: str, unit: Units = Units.FAHRENHEIT) -> float:
        ...     '''Get temperature for a city.'''
        ...     return 72.0

        >>> temp_tool = create_tool_from_function(get_temperature)
    """
    # Import here to avoid circular imports
    from dapr.clients.grpc._request import ConversationToolsFunction, ConversationTools

    # Generate JSON schema from function
    json_schema = function_to_json_schema(func, name, description)

    # Use provided name or function name
    tool_name = name or func.__name__

    # Use provided description or extract from function
    tool_description = description
    if tool_description is None:
        docstring = inspect.getdoc(func)
        if docstring:
            tool_description = docstring.split('\n')[0].strip()
        else:
            tool_description = f'Function {tool_name}'

    # Create the tool function
    function = ConversationToolsFunction(
        name=tool_name, description=tool_description, parameters=json_schema
    )

    # Return the complete tool
    return ConversationTools(function=function)
