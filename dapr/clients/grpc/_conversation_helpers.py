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
import random
import string
from dataclasses import fields, is_dataclass
from enum import Enum
from typing import (
    Any,
    Callable,
    Dict,
    List,
    Mapping,
    Optional,
    Sequence,
    Union,
    Literal,
    get_args,
    get_origin,
    get_type_hints,
    cast,
)

from dapr.conf import settings

import types

# Make mypy happy. Runtime handle: real class on 3.10+, else None.
# TODO: Python 3.9 is about to be end-of-life, so we can drop this at some point next year (2026)
UnionType: Any = getattr(types, 'UnionType', None)

# duplicated from conversation to avoid circular import
Params = Union[Mapping[str, Any], Sequence[Any], None]

"""
Tool Calling Helpers for Dapr Conversation API.

This module provides function-to-JSON-schema helpers that automatically
convert typed Python functions to tools for the Conversation API.

These makes it easy to create tools for the Conversation API without
having to manually define the JSON schema for each tool.
"""


def _python_type_to_json_schema(python_type: Any, field_name: str = '') -> Dict[str, Any]:
    """Convert a Python type hint to JSON schema format.

    Args:
        python_type: The Python type to convert
        field_name: The name of the field (for better error messages)

    Returns:
        Dict representing the JSON schema for this type

    Examples:
        >>> _python_type_to_json_schema(str)
        {"type": "string"}
        >>> _python_type_to_json_schema(Optional[int])
        {"type": "integer"}
        >>> _python_type_to_json_schema(List[str])
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
            return _python_type_to_json_schema(non_none_args[0], field_name)
        else:
            # This is a true Union, use anyOf
            return {'anyOf': [_python_type_to_json_schema(arg, field_name) for arg in args]}

    # Handle Literal types -> map to enum
    if origin is Literal:
        # Normalize literal values (convert Enum members to their value)
        literal_values: List[Any] = []
        for val in args:
            try:
                from enum import Enum as _Enum

                if isinstance(val, _Enum):
                    literal_values.append(val.value)
                else:
                    literal_values.append(val)
            except Exception:
                literal_values.append(val)

        # Determine JSON Schema primitive types for provided literals
        def _json_primitive_type(v: Any) -> str:
            if v is None:
                return 'null'
            if isinstance(v, bool):
                return 'boolean'
            if isinstance(v, int) and not isinstance(v, bool):
                return 'integer'
            if isinstance(v, float):
                return 'number'
            if isinstance(v, (bytes, bytearray)):
                return 'string'
            if isinstance(v, str):
                return 'string'
            # Fallback: let enum carry through without explicit type
            return 'string'

        types = {_json_primitive_type(v) for v in literal_values}
        schema: Dict[str, Any] = {'enum': literal_values}
        # If all non-null literals share same type, include it
        non_null_types = {t for t in types if t != 'null'}
        if len(non_null_types) == 1 and (len(types) == 1 or len(types) == 2 and 'null' in types):
            only_type = next(iter(non_null_types)) if non_null_types else 'null'
            if only_type == 'string' and any(
                isinstance(v, (bytes, bytearray)) for v in literal_values
            ):
                schema['type'] = 'string'
                # Note: bytes literals represented as raw bytes are unusual; keeping enum as-is.
            else:
                schema['type'] = only_type
        elif types == {'null'}:
            schema['type'] = 'null'
        return schema

    # Handle List types
    if origin is list or python_type is list:
        if args:
            return {
                'type': 'array',
                'items': _python_type_to_json_schema(args[0], f'{field_name}[]'),
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
                schema['additionalProperties'] = _python_type_to_json_schema(
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
        try:
            members = list(python_type)
        except Exception:
            members = []
        count = len(members)
        # If enum is small enough, include full enum list (current behavior)
        if count <= settings.DAPR_CONVERSATION_TOOLS_MAX_ENUM_ITEMS:
            return {'type': 'string', 'enum': [item.value for item in members]}
        # Large enum handling
        if settings.DAPR_CONVERSATION_TOOLS_LARGE_ENUM_BEHAVIOR == 'error':
            raise ValueError(
                f"Enum '{getattr(python_type, '__name__', str(python_type))}' has {count} members, "
                f"exceeding DAPR_CONVERSATION_MAX_ENUM_ITEMS={settings.DAPR_CONVERSATION_TOOLS_MAX_ENUM_ITEMS}. "
                f"Either reduce the enum size or set DAPR_CONVERSATION_LARGE_ENUM_BEHAVIOR=string to allow compact schema."
            )
        # Default behavior: compact schema as a string with helpful context and a few examples
        example_values = [item.value for item in members[:5]] if members else []
        desc = (
            f"{getattr(python_type, '__name__', 'Enum')} (enum with {count} values). "
            f"Provide a valid value. Schema compacted to avoid oversized enum listing."
        )
        schema = {'type': 'string', 'description': desc}
        if example_values:
            schema['examples'] = example_values
        return schema

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

        dataclass_schema: Dict[str, Any] = {'type': 'object', 'properties': {}, 'required': []}

        for field in fields(python_type):
            field_schema = _python_type_to_json_schema(field.type, field.name)
            dataclass_schema['properties'][field.name] = field_schema

            # Check if field has no default (required) - use MISSING for dataclasses
            if field.default is MISSING:
                dataclass_schema['required'].append(field.name)

        return dataclass_schema

    # Handle plain classes (non-dataclass) using __init__ signature and annotations
    if inspect.isclass(python_type) and python_type is not Any:
        try:
            # Gather type hints from __init__ if available; fall back to class annotations
            init = getattr(python_type, '__init__', None)
            init_hints = get_type_hints(init) if init else {}
            class_hints = get_type_hints(python_type)
        except Exception:
            init_hints = {}
            class_hints = {}

        # Build properties from __init__ parameters (excluding self)
        properties: Dict[str, Any] = {}
        required: List[str] = []

        try:
            sig = inspect.signature(python_type)
        except Exception:
            sig = None  # type: ignore

        check_slots = True
        if sig is not None:
            check_slots = False
            for pname, param in sig.parameters.items():
                if pname == 'self':
                    continue
                # Determine type for this parameter
                ptype = init_hints.get(pname) or class_hints.get(pname) or Any
                properties[pname] = _python_type_to_json_schema(ptype, pname)
                # Required if no default provided and not VAR_KEYWORD/POSITIONAL
                if param.default is inspect._empty and param.kind in (
                    inspect.Parameter.POSITIONAL_ONLY,
                    inspect.Parameter.POSITIONAL_OR_KEYWORD,
                    inspect.Parameter.KEYWORD_ONLY,
                ):
                    required.append(pname)
            else:
                check_slots = True
        if check_slots:
            # Fall back to __slots__ if present
            slots = getattr(python_type, '__slots__', None)
            if isinstance(slots, (list, tuple)):
                for pname in slots:
                    ptype = class_hints.get(pname, Any)
                    properties[pname] = _python_type_to_json_schema(ptype, pname)
                    if not (get_origin(ptype) is Union and type(None) in get_args(ptype)):
                        required.append(pname)
            else:  # use class_hints
                for pname, ptype in class_hints.items():
                    properties[pname] = _python_type_to_json_schema(ptype, pname)
                    if not (get_origin(ptype) is Union and type(None) in get_args(ptype)):
                        required.append(pname)

        # If we found nothing, return a generic object
        if not properties:
            return {'type': 'object'}

        schema = {'type': 'object', 'properties': properties}
        if required:
            schema['required'] = required
        return schema

    # Fallback for unknown/unsupported types
    raise TypeError(
        f"Unsupported type in JSON schema conversion for field '{field_name}': {python_type}. "
        f'Please use supported typing annotations (e.g., str, int, float, bool, bytes, List[T], Dict[str, V], Union, Optional, Literal, Enum, dataclass, or plain classes).'
        f'You can report this issue for future support of this type. You can always create the json schema manually.'
    )


def _extract_docstring_args(func) -> Dict[str, str]:
    """Extract parameter descriptions from function docstring.

    Supports Google-style, NumPy-style, and Sphinx-style docstrings.

    Args:
        func: The function to analyze

    Returns:
        Dict mapping parameter names to their descriptions

    Raises:
        ValueError: If docstring contains parameter info but doesn't match supported formats
    """
    docstring = inspect.getdoc(func)
    if not docstring:
        return {}

    param_descriptions = {}
    lines = docstring.split('\n')

    # First, try to extract Sphinx-style parameters (:param name: description)
    param_descriptions.update(_extract_sphinx_params(lines))

    # If no Sphinx-style params found, try Google/NumPy style
    if not param_descriptions:
        param_descriptions.update(_extract_google_numpy_params(lines))

    # If still no parameters found, check if docstring might have parameter info
    # in an unsupported format
    if not param_descriptions and _has_potential_param_info(lines):
        func_name = getattr(func, '__name__', 'unknown')
        import warnings

        warnings.warn(
            f"Function '{func_name}' has a docstring that appears to contain parameter "
            f"information, but it doesn't match any supported format (Google, NumPy, or Sphinx style). "
            f'Consider reformatting the docstring to use one of the supported styles for '
            f'automatic parameter extraction or create the tool manually.',
            UserWarning,
            stacklevel=2,
        )

    return param_descriptions


def _has_potential_param_info(lines: List[str]) -> bool:
    """Check if docstring lines might contain parameter information in unsupported format.

    This is a heuristic to detect when a docstring might have parameter info
    but doesn't match our supported formats (Google, NumPy, Sphinx).
    """
    text = ' '.join(line.strip().lower() for line in lines)

    # Look for specific parameter documentation patterns that suggest
    # an attempt to document parameters in an unsupported format
    import re

    # Look for informal parameter descriptions like:
    # "The filename parameter should be..." or "parameter_name is used for..."
    has_param_descriptions = bool(
        re.search(r'the\s+\w+\s+parameter\s+(should|is|controls|specifies)', text)
    )

    # Look for patterns where parameters are mentioned with descriptions
    # "filename parameter", "mode parameter", etc.
    has_param_mentions = bool(
        re.search(r'\w+\s+parameter\s+(should|is|controls|specifies|contains)', text)
    )

    # Look for informal patterns like "takes param1 which is", "param2 is an integer"
    has_informal_param_descriptions = bool(
        re.search(r'takes\s+\w+\s+which\s+(is|are)', text)
        or re.search(r'\w+\s+(is|are)\s+(a|an)\s+\w+\s+(input|argument)', text)
    )

    # Look for multiple parameter mentions suggesting documentation attempt
    param_count = text.count(' parameter ')
    has_multiple_param_mentions = param_count >= 2

    # Exclude common phrases that don't indicate parameter documentation attempts
    exclude_phrases = [
        'no parameters',
        'without parameters',
        'parameters documented',
        'parameter information',
        'parameter extraction',
        'function parameter',
        'optional parameter',
        'required parameter',  # These are often in general descriptions
    ]
    has_excluded_phrases = any(phrase in text for phrase in exclude_phrases)

    return (
        has_param_descriptions
        or has_param_mentions
        or has_informal_param_descriptions
        or has_multiple_param_mentions
    ) and not has_excluded_phrases


def _extract_sphinx_params(lines: List[str]) -> Dict[str, str]:
    """Extract parameters from Sphinx-style docstring.

    Looks for patterns like:
    :param name: description
    :parameter name: description
    """
    import re

    param_descriptions = {}

    for original_line in lines:
        line = original_line.strip()

        # Match Sphinx-style parameter documentation
        # Patterns: :param name: description or :parameter name: description
        param_match = re.match(r':param(?:eter)?\s+(\w+)\s*:\s*(.*)', line)
        if param_match:
            param_name = param_match.group(1)
            description = param_match.group(2).strip()
            param_descriptions[param_name] = description
            continue

        # Handle multi-line descriptions for Sphinx style
        # If line is indented and we have existing params, it might be a continuation
        if (
            original_line.startswith('    ') or original_line.startswith('\t')
        ) and param_descriptions:
            # Check if this could be a continuation of the last parameter
            last_param = list(param_descriptions.keys())[-1]
            # Don't treat section headers or other directive-like content as continuations
            # Also don't treat content that looks like parameter definitions from other styles
            if (
                param_descriptions[last_param]
                and not any(
                    line.startswith(prefix) for prefix in [':param', ':type', ':return', ':raises']
                )
                and not line.lower().endswith(':')
                and not line.lower() in ('args', 'arguments', 'parameters', 'params')
                and ':' not in line
            ):  # Avoid treating "param1: description" as continuation
                param_descriptions[last_param] += ' ' + line.strip()

    return param_descriptions


def _extract_google_numpy_params(lines: List[str]) -> Dict[str, str]:
    """Extract parameters from Google/NumPy-style docstring."""
    param_descriptions = {}
    in_args_section = False
    current_param = None

    for i, original_line in enumerate(lines):
        line = original_line.strip()

        # Detect Args/Parameters section
        if line.lower() in ('args:', 'arguments:', 'parameters:', 'params:'):
            in_args_section = True
            continue

        # Handle NumPy style section headers with dashes
        if line.lower() in ('parameters', 'arguments') and in_args_section is False:
            in_args_section = True
            continue

        # Skip NumPy-style separator lines (dashes) but also check if this signals section end
        if in_args_section and line and all(c in '-=' for c in line):
            # Check if next line starts a new section
            next_line_idx = i + 1
            if next_line_idx < len(lines):
                next_line = lines[next_line_idx].strip().lower()
                if next_line in (
                    'returns',
                    'return',
                    'yields',
                    'yield',
                    'raises',
                    'raise',
                    'notes',
                    'note',
                    'examples',
                    'example',
                ):
                    in_args_section = False
            continue

        # Exit args section on new section
        if in_args_section and (line.endswith(':') and not line.startswith(' ')):
            in_args_section = False
            continue

        # Also exit on direct section headers without separators
        if in_args_section and line.lower() in (
            'returns',
            'return',
            'yields',
            'yield',
            'raises',
            'raise',
            'notes',
            'note',
            'examples',
            'example',
        ):
            in_args_section = False
            continue

        if in_args_section and line:
            # Look for parameter definitions (contains colon)
            if ':' in line:
                parts = line.split(':', 1)
                if len(parts) == 2:
                    param_name = parts[0].strip()
                    description = parts[1].strip()

                    # Handle type annotations like "param_name (type): description"
                    if '(' in param_name and ')' in param_name:
                        param_name = param_name.split('(')[0].strip()
                    # Handle NumPy style "param_name : type" format where description is on next line
                    if ' ' in param_name:
                        param_name = param_name.split()[0]

                    # Check if this looks like a real description vs just a type annotation
                    # For NumPy style: "param : type" vs Google style: "param: description"
                    # Type annotations are usually single words like "str", "int", "float"
                    # Descriptions have multiple words or punctuation
                    if description:
                        if description.replace(' ', '').isalnum() and len(description.split()) == 1:
                            # Likely just a type annotation (single alphanumeric word), wait for real description
                            param_descriptions[param_name] = ''
                        else:
                            # Contains multiple words or punctuation, likely a real description
                            param_descriptions[param_name] = description
                    else:
                        param_descriptions[param_name] = ''
                    current_param = param_name
            elif (
                current_param
                and (original_line.startswith('    ') or original_line.startswith('\t'))
                and in_args_section
            ):
                # Indented continuation line for current parameter (only if still in args section)
                if not param_descriptions[current_param]:
                    # First description line for this parameter (for cases where description is on next line)
                    param_descriptions[current_param] = line
                else:
                    # Additional description lines
                    param_descriptions[current_param] += ' ' + line

    return param_descriptions


def extract_docstring_summary(func) -> Optional[str]:
    """Extract only the summary from a function's docstring.

    Args:
        func: The function to extract the summary from

    Returns:
        The summary portion of the docstring, or None if no docstring exists
    """
    docstring = inspect.getdoc(func)
    if not docstring:
        return None

    lines = docstring.strip().split('\n')
    if not lines:
        return None

    # Extract all lines before the first section header
    summary_lines = []

    for line in lines:
        line = line.strip()

        # Skip empty lines
        if not line:
            continue

        # Check if this line starts a Google/NumPy-style section
        google_numpy_headers = (
            'args:',
            'arguments:',
            'parameters:',
            'params:',
            'returns:',
            'return:',
            'yields:',
            'yield:',
            'raises:',
            'raise:',
            'note:',
            'notes:',
            'example:',
            'examples:',
            'see also:',
            'references:',
            'attributes:',
        )
        if line.lower().endswith(':') and line.lower() in google_numpy_headers:
            break

        # Check if this line starts a Sphinx-style section
        # Look for patterns like :param name:, :returns:, :raises:, etc.
        import re

        sphinx_pattern = r'^:(?:param|parameter|type|returns?|return|yields?|yield|raises?|raise|note|notes|example|examples|see|seealso|references?|attributes?)(?:\s+\w+)?:'
        if re.match(sphinx_pattern, line.lower()):
            break

        summary_lines.append(line)

    return ' '.join(summary_lines) if summary_lines else None


def function_to_json_schema(
    func, name: Optional[str] = None, description: Optional[str] = None
) -> Dict[str, Any]:
    """Convert a Python function to a JSON schema for tool calling.
    All parameters without default values are set as required.

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
    param_descriptions = _extract_docstring_args(func)

    # Build JSON schema
    schema: Dict[str, Any] = {'type': 'object', 'properties': {}, 'required': []}

    for param_name, param in sig.parameters.items():
        # Skip *args and **kwargs
        if param.kind in (param.VAR_POSITIONAL, param.VAR_KEYWORD):
            continue

        # Get type hint
        param_type = type_hints.get(param_name, str)

        # Convert to JSON schema
        param_schema = _python_type_to_json_schema(param_type, param_name)

        # Add description if available
        if param_name in param_descriptions:
            param_schema['description'] = param_descriptions[param_name]

        schema['properties'][param_name] = param_schema

        # Check if parameter is required (no default value)
        if param.default is param.empty:
            schema['required'].append(param_name)

    return schema


def _generate_unique_tool_call_id():
    """Generate a unique ID for a tool call.  Mainly used if the LLM provider is not able to generate one itself."""
    return ''.join(random.choices(string.ascii_letters + string.digits, k=9))


def stringify_tool_output(value: Any) -> str:
    """Convert arbitrary tool return values into a serializable string.

    Rules:
    - If value is already a string, return as-is.
    - For bytes/bytearray, return a base64-encoded string with 'base64:' prefix (not JSON).
    - Otherwise, attempt to JSON-serialize the value and return the JSON string.
      Uses a conservative default encoder that supports only:
        * Enum -> enum.value (fallback to name)
        * dataclass -> asdict
      If JSON serialization still fails, fallback to str(value). If that fails, return '<unserializable>'.
    """
    import json as _json
    import base64 as _b64
    from dataclasses import asdict as _asdict

    if isinstance(value, str):
        return value

    # bytes/bytearray -> base64 string (raw, not JSON-quoted)
    if isinstance(value, (bytes, bytearray)):
        try:
            return 'base64:' + _b64.b64encode(bytes(value)).decode('ascii')
        except Exception:
            try:
                return str(value)
            except Exception:
                return '<unserializable>'

    def _default(o: Any):
        # Enum handling
        try:
            from enum import Enum as _Enum

            if isinstance(o, _Enum):
                try:
                    return o.value
                except Exception:
                    return getattr(o, 'name', str(o))
        except Exception:
            pass

        # dataclass handling
        try:
            if is_dataclass(o):
                # mypy: asdict expects a DataclassInstance; after the runtime guard, this cast is safe
                return _asdict(cast(Any, o))
        except Exception:
            pass

        # Plain Python objects with __dict__: return a dict filtered for non-callable attributes
        try:
            d = getattr(o, '__dict__', None)
            if isinstance(d, dict):
                return {k: v for k, v in d.items() if not callable(v)}
        except Exception:
            pass

        # Fallback: cause JSON to fail for unsupported types
        raise TypeError(f'Object of type {type(o).__name__} is not JSON serializable')

    try:
        return _json.dumps(value, default=_default, ensure_ascii=False)
    except Exception:
        try:
            # Last resort: convert to string
            return str(value)
        except Exception:
            return '<unserializable>'


# --- Tool Function Executor Backend

# --- Errors ----


class ToolError(RuntimeError):
    ...


class ToolNotFoundError(ToolError):
    ...


class ToolExecutionError(ToolError):
    ...


class ToolArgumentError(ToolError):
    ...


def _coerce_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int,)):
        return bool(value)
    if isinstance(value, str):
        v = value.strip().lower()
        if v in {'true', '1', 'yes', 'y', 'on'}:
            return True
        if v in {'false', '0', 'no', 'n', 'off'}:
            return False
    raise ValueError(f'Cannot coerce to bool: {value!r}')


def _coerce_scalar(value: Any, expected_type: Any) -> Any:
    # Basic scalar coercions
    if expected_type is str:
        return value if isinstance(value, str) else str(value)
    if expected_type is int:
        if isinstance(value, bool):  # avoid True->1 surprises
            return int(value)
        if isinstance(value, int):
            return value
        if isinstance(value, (float,)) and value.is_integer():
            return int(value)
        if isinstance(value, str):
            return int(value.strip())
        raise ValueError
    if expected_type is float:
        if isinstance(value, (int, float)):
            return float(value)
        if isinstance(value, str):
            return float(value.strip())
        raise ValueError
    if expected_type is bool:
        return _coerce_bool(value)
    return value


def _coerce_enum(value: Any, enum_type: Any) -> Any:
    # Accept enum instance, name, or value
    if isinstance(value, enum_type):
        return value
    try:
        # match by value
        for member in enum_type:
            if member.value == value:
                return member
        if isinstance(value, str):
            name = value.strip()
            try:
                return enum_type[name]
            except Exception:
                # try case-insensitive
                for member in enum_type:
                    if member.name.lower() == name.lower():
                        return member
    except Exception:
        pass
    raise ValueError(f'Cannot coerce {value!r} to {enum_type.__name__}')


def _coerce_literal(value: Any, lit_args: List[Any]) -> Any:
    # Try exact match first
    if value in lit_args:
        return value
    # Try string-to-number coercions if literal set is homogeneous numeric
    try_coerced: List[Any] = []
    for target in lit_args:
        try:
            if isinstance(target, int) and not isinstance(target, bool) and isinstance(value, str):
                try_coerced.append(int(value))
            elif isinstance(target, float) and isinstance(value, str):
                try_coerced.append(float(value))
            else:
                try_coerced.append(value)
        except Exception:
            try_coerced.append(value)
    for coerced in try_coerced:
        if coerced in lit_args:
            return coerced
    raise ValueError(f'{value!r} not in allowed literals {lit_args!r}')


def _is_union(t) -> bool:
    origin = get_origin(t)
    if origin is Union:
        return True
    return UnionType is not None and origin is UnionType


def _coerce_and_validate(value: Any, expected_type: Any) -> Any:
    args = get_args(expected_type)

    if expected_type is Any:
        raise TypeError('We cannot handle parameters with type Any')

    # Optional[T] -> Union[T, None]
    if _is_union(expected_type):
        # try each option
        last_err: Optional[Exception] = None
        for opt in args:
            if opt is type(None):
                if value is None:
                    return None
                continue
            try:
                return _coerce_and_validate(value, opt)
            except Exception as e:
                last_err = e
                continue
        raise ValueError(
            str(last_err) if last_err else f'Cannot coerce {value!r} to {expected_type}'
        )

    origin = get_origin(expected_type)

    # Literal
    if origin is Literal:
        return _coerce_literal(value, list(args))

    # List[T]
    if origin is list or expected_type is list:
        item_type = args[0] if args else Any
        if not isinstance(value, list):
            raise ValueError(f'Expected list, got {type(value).__name__}')
        return [_coerce_and_validate(v, item_type) for v in value]

    # Dict[K, V]
    if origin is dict or expected_type is dict:
        key_t = args[0] if len(args) > 0 else Any
        val_t = args[1] if len(args) > 1 else Any
        if not isinstance(value, dict):
            raise ValueError(f'Expected dict, got {type(value).__name__}')
        coerced: Dict[Any, Any] = {}
        for k, v in value.items():
            ck = _coerce_and_validate(k, key_t)
            cv = _coerce_and_validate(v, val_t)
            coerced[ck] = cv
        return coerced

    # Enums
    if inspect.isclass(expected_type) and issubclass(expected_type, Enum):
        return _coerce_enum(value, expected_type)

    # Dataclasses
    if inspect.isclass(expected_type) and is_dataclass(expected_type):
        if isinstance(value, expected_type) or value is None:
            return value
        raise ValueError(
            f'Expected {expected_type.__name__} dataclass instance, got {type(value).__name__}'
        )

    # Plain classes (construct from dict using __init__ where possible)
    if inspect.isclass(expected_type):
        if isinstance(value, expected_type):
            return value
        if isinstance(value, dict):
            try:
                sig = inspect.signature(expected_type)
            except Exception as e:
                raise ValueError(f'Cannot inspect constructor for {expected_type.__name__}: {e}')

            # type hints from __init__
            try:
                init_hints = get_type_hints(getattr(expected_type, '__init__', None))
            except Exception:
                init_hints = {}

            kwargs: Dict[str, Any] = {}
            missing: List[str] = []
            for pname, param in sig.parameters.items():
                if pname == 'self':
                    continue
                if pname in value:
                    et = init_hints.get(pname, Any)
                    kwargs[pname] = _coerce_and_validate(value[pname], et)
                else:
                    if param.default is inspect._empty and param.kind in (
                        inspect.Parameter.POSITIONAL_ONLY,
                        inspect.Parameter.POSITIONAL_OR_KEYWORD,
                        inspect.Parameter.KEYWORD_ONLY,
                    ):
                        missing.append(pname)
            if missing:
                raise ValueError(
                    f"Missing required constructor arg(s) for {expected_type.__name__}: {', '.join(missing)}"
                )
            try:
                return expected_type(**kwargs)
            except Exception as e:
                raise ValueError(f'Failed constructing {expected_type.__name__} with {kwargs}: {e}')
        # Not a dict or instance: fall through to isinstance check

    # Basic primitives
    try:
        return _coerce_scalar(value, expected_type)
    except Exception:
        # Fallback to isinstance check
        if expected_type is Any or isinstance(value, expected_type):
            return value
        raise ValueError(
            f"Expected {getattr(expected_type, '__name__', str(expected_type))}, got {type(value).__name__}"
        )


def bind_params_to_func(fn: Callable[..., Any], params: Params):
    """Bind parameters to a function in the correct order.

    Args:
        fn: The function to bind parameters to
        params: The parameters to bind

    Returns:
        The bound parameters
    """
    sig = inspect.signature(fn)
    if params is None:
        bound = sig.bind()
        bound.apply_defaults()
        return bound

    if isinstance(params, Mapping):
        bound = sig.bind_partial(**params)
        # missing required parameters
        missing = [
            p.name
            for p in sig.parameters.values()
            if p.default is inspect._empty
            and p.kind
            in (
                inspect.Parameter.POSITIONAL_ONLY,
                inspect.Parameter.POSITIONAL_OR_KEYWORD,
                inspect.Parameter.KEYWORD_ONLY,
            )
            and p.name not in bound.arguments
        ]
        if missing:
            raise ToolArgumentError(f"Missing required parameter(s): {', '.join(missing)}")
        # unexpected kwargs unless **kwargs present
        if not any(p.kind is inspect.Parameter.VAR_KEYWORD for p in sig.parameters.values()):
            extra = set(params) - set(sig.parameters)
            if extra:
                raise ToolArgumentError(f"Unexpected parameter(s): {', '.join(sorted(extra))}")
    elif isinstance(params, Sequence):
        bound = sig.bind(*params)
    else:
        raise ToolArgumentError('params must be a mapping (kwargs), sequence (positional), or None')

    bound.apply_defaults()

    # Coerce and validate according to type hints
    try:
        type_hints = get_type_hints(fn)
    except Exception:
        type_hints = {}
    for name, value in list(bound.arguments.items()):
        if name in type_hints:
            expected = type_hints[name]
            try:
                bound.arguments[name] = _coerce_and_validate(value, expected)
            except Exception as e:
                raise ToolArgumentError(
                    f"Invalid value for parameter '{name}': expected {getattr(get_origin(expected) or expected, '__name__', str(expected))}, got {type(value).__name__} ({value!r}). Details: {e}"
                ) from e

    return bound
