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
    get_args,
    get_origin,
    get_type_hints,
)

from dapr.clients.grpc.conversation import Params

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
        schema: Dict[str, Any] = {'type': 'object'}
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

        dataclass_schema: Dict[str, Any] = {'type': 'object', 'properties': {}, 'required': []}

        for field in fields(python_type):
            field_schema = _python_type_to_json_schema(field.type, field.name)
            dataclass_schema['properties'][field.name] = field_schema

            # Check if field has no default (required) - use MISSING for dataclasses
            if field.default is MISSING:
                dataclass_schema['required'].append(field.name)

        return dataclass_schema

    # Fallback for unknown types
    return {'type': 'string', 'description': f'Unknown type: {python_type}'}


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

    # Get function description
    if description is None:
        docstring = inspect.getdoc(func)
        if docstring:
            # Use first line of docstring as description
            description = docstring.split('\n')[0].strip()
        else:
            description = f'Function {func.__name__}'

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
    return bound
