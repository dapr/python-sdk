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
from typing import Any, Dict, List, Optional, Type

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


# TODO(@sicoyle): see if I can remove this and use something from official modelcontextprotocol python-sdk instead???
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
                if non_null_variants:
                    primary_type = non_null_variants[0].get('type', 'string')
                    field_type = TYPE_MAPPING.get(primary_type, str)
                    if primary_type == 'array' and 'items' in non_null_variants[0]:
                        item_type = non_null_variants[0]['items'].get('type', 'string')
                        field_type = List[TYPE_MAPPING.get(item_type, str)]
                    elif primary_type == 'object':
                        field_type = dict
                else:
                    field_type = str
                if has_null:
                    field_type = Optional[field_type]
            else:
                json_type = field_props.get('type', 'string')
                field_type = TYPE_MAPPING.get(json_type, str)
                if json_type == 'array' and 'items' in field_props:
                    item_type = field_props['items'].get('type', 'string')
                    field_type = List[TYPE_MAPPING.get(item_type, str)]

            if field_name in required:
                default = ...
            else:
                default = None
                if not (hasattr(field_type, '__origin__') and field_type.__origin__ is Optional):
                    field_type = Optional[field_type]

            field_description = field_props.get('description', '')
            fields[field_name] = (
                field_type,
                Field(default, description=field_description),
            )

        return create_model(model_name, **fields)

    except Exception as e:
        logger.error('Failed to create model from schema: %s', e)
        raise ValueError(f'Invalid schema: {e}') from e
