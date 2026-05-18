# -*- coding: utf-8 -*-

# Copyright 2026 The Dapr Authors
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#     http://www.apache.org/licenses/LICENSE-2.0
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Utility for converting MCP JSON Schema definitions to Pydantic models."""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Type, Union, get_args, get_origin

from pydantic import BaseModel, Field, create_model

logger = logging.getLogger(__name__)

# Mapping from JSON Schema types to Python types.
TYPE_MAPPING = {
    'string': str,
    'number': float,
    'integer': int,
    'boolean': bool,
    'object': dict,
    'array': list,
    'null': type(None),
}


def create_pydantic_model_from_schema(schema: Dict[str, Any], model_name: str) -> Type[BaseModel]:
    """Create a Pydantic model from a JSON Schema definition.

    This function converts a JSON Schema object (commonly used in MCP tool
    definitions) to a Pydantic model that can be used for argument validation.

    Args:
        schema: JSON Schema dictionary containing type information.
        model_name: Name for the generated model class.

    Returns:
        A dynamically created Pydantic model class.

    Raises:
        ValueError: If the schema is invalid or cannot be converted.
    """
    logger.debug("Creating Pydantic model '%s' from schema", model_name)

    try:
        properties = schema.get('properties', {})
        required = set(schema.get('required', []))

        # Handle schemas that wrap arguments in a 'kwargs' field.
        # Some MCP tools use this pattern — unwrap to accept flat arguments.
        if (
            len(properties) == 1
            and 'kwargs' in properties
            and properties['kwargs'].get('type') == 'object'
            and 'properties' in properties['kwargs']
        ):
            logger.debug("Detected 'kwargs' wrapper in schema for '%s', unwrapping", model_name)
            kwargs_schema = properties['kwargs']
            properties = kwargs_schema['properties']
            required = set(kwargs_schema.get('required', []))

        fields: Dict[str, Any] = {}

        for field_name, field_props in properties.items():
            # Handle anyOf/oneOf for nullable/union fields.
            if 'anyOf' in field_props or 'oneOf' in field_props:
                variants = field_props.get('anyOf') or field_props.get('oneOf')
                types = [v.get('type', 'string') for v in variants]
                has_null = 'null' in types
                non_null_variants = [v for v in variants if v.get('type') != 'null']
                variant_types: List[Any] = []
                for v in non_null_variants:
                    v_type = v.get('type', 'string')
                    # JSON Schema allows "type" to be a list (e.g. ["string", "null"]).
                    # Pick the first non-null element so we have a hashable scalar.
                    if isinstance(v_type, list):
                        non_null = [t for t in v_type if t != 'null']
                        v_type = non_null[0] if non_null else 'string'
                    if v_type == 'array' and 'items' in v:
                        item_type = v['items'].get('type', 'string')
                        if isinstance(item_type, list):
                            item_type = next((t for t in item_type if t != 'null'), 'string')
                        variant_types.append(List[TYPE_MAPPING.get(item_type, str)])
                    elif v_type == 'object':
                        variant_types.append(dict)
                    else:
                        variant_types.append(TYPE_MAPPING.get(v_type, str))
                if not variant_types:
                    field_type = str
                elif len(variant_types) == 1:
                    field_type = variant_types[0]
                else:
                    field_type = Union[tuple(variant_types)]  # type: ignore[assignment]
                if has_null:
                    field_type = Optional[field_type]
            else:
                json_type = field_props.get('type', 'string')
                # Same list-type handling as above.
                if isinstance(json_type, list):
                    non_null = [t for t in json_type if t != 'null']
                    json_type = non_null[0] if non_null else 'string'
                field_type = TYPE_MAPPING.get(json_type, str)
                if json_type == 'array' and 'items' in field_props:
                    item_type = field_props['items'].get('type', 'string')
                    if isinstance(item_type, list):
                        item_type = next((t for t in item_type if t != 'null'), 'string')
                    field_type = List[TYPE_MAPPING.get(item_type, str)]

            if field_name in required:
                default = ...
            else:
                default = None
                # Wrap in Optional[...] unless the type is already a Union that includes NoneType
                # (e.g. produced by an anyOf with a 'null' variant above).
                if type(None) not in get_args(field_type) or get_origin(field_type) is not Union:
                    field_type = Optional[field_type]

            field_description = field_props.get('description', '')
            fields[field_name] = (
                field_type,
                Field(default, description=field_description),
            )

        return create_model(model_name, **fields)

    except Exception as e:
        logger.exception('Failed to create model from schema')
        raise ValueError(f'Invalid schema: {e}') from e
