# -*- coding: utf-8 -*-

"""
Copyright 2026 The Dapr Authors
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

import unittest

from pydantic import BaseModel

from dapr.ext.workflow.mcp_schema import create_pydantic_model_from_schema


class TestBasicTypes(unittest.TestCase):
    """Tests for basic JSON Schema type conversions."""

    def test_string_field(self):
        schema = {
            'type': 'object',
            'properties': {'name': {'type': 'string', 'description': 'A name'}},
            'required': ['name'],
        }
        Model = create_pydantic_model_from_schema(schema, 'TestModel')
        instance = Model(name='Alice')
        self.assertEqual(instance.name, 'Alice')

    def test_integer_field(self):
        schema = {
            'type': 'object',
            'properties': {'count': {'type': 'integer'}},
            'required': ['count'],
        }
        Model = create_pydantic_model_from_schema(schema, 'IntModel')
        instance = Model(count=42)
        self.assertEqual(instance.count, 42)

    def test_number_field(self):
        schema = {
            'type': 'object',
            'properties': {'price': {'type': 'number'}},
            'required': ['price'],
        }
        Model = create_pydantic_model_from_schema(schema, 'NumModel')
        instance = Model(price=9.99)
        self.assertAlmostEqual(instance.price, 9.99)

    def test_boolean_field(self):
        schema = {
            'type': 'object',
            'properties': {'active': {'type': 'boolean'}},
            'required': ['active'],
        }
        Model = create_pydantic_model_from_schema(schema, 'BoolModel')
        instance = Model(active=True)
        self.assertTrue(instance.active)

    def test_array_field(self):
        schema = {
            'type': 'object',
            'properties': {'tags': {'type': 'array', 'items': {'type': 'string'}}},
            'required': ['tags'],
        }
        Model = create_pydantic_model_from_schema(schema, 'ArrayModel')
        instance = Model(tags=['a', 'b'])
        self.assertEqual(instance.tags, ['a', 'b'])


class TestRequiredOptional(unittest.TestCase):
    """Tests for required vs optional field handling."""

    def test_required_field_has_no_default(self):
        schema = {
            'type': 'object',
            'properties': {'location': {'type': 'string'}},
            'required': ['location'],
        }
        Model = create_pydantic_model_from_schema(schema, 'ReqModel')
        with self.assertRaises(Exception):
            Model()  # Missing required field

    def test_optional_field_defaults_to_none(self):
        schema = {
            'type': 'object',
            'properties': {'location': {'type': 'string'}},
            'required': [],
        }
        Model = create_pydantic_model_from_schema(schema, 'OptModel')
        instance = Model()
        self.assertIsNone(instance.location)

    def test_mixed_required_optional(self):
        schema = {
            'type': 'object',
            'properties': {
                'location': {'type': 'string'},
                'days': {'type': 'integer'},
            },
            'required': ['location'],
        }
        Model = create_pydantic_model_from_schema(schema, 'MixedModel')
        instance = Model(location='Tokyo')
        self.assertEqual(instance.location, 'Tokyo')
        self.assertIsNone(instance.days)


class TestAnyOfOneOf(unittest.TestCase):
    """Tests for anyOf/oneOf nullable/union field handling."""

    def test_anyof_nullable_string(self):
        schema = {
            'type': 'object',
            'properties': {
                'label': {
                    'anyOf': [
                        {'type': 'string'},
                        {'type': 'null'},
                    ]
                }
            },
            'required': ['label'],
        }
        Model = create_pydantic_model_from_schema(schema, 'NullableModel')
        instance = Model(label=None)
        self.assertIsNone(instance.label)
        instance2 = Model(label='hello')
        self.assertEqual(instance2.label, 'hello')

    def test_oneof_nullable_integer(self):
        schema = {
            'type': 'object',
            'properties': {
                'count': {
                    'oneOf': [
                        {'type': 'integer'},
                        {'type': 'null'},
                    ]
                }
            },
            'required': ['count'],
        }
        Model = create_pydantic_model_from_schema(schema, 'OneOfModel')
        instance = Model(count=5)
        self.assertEqual(instance.count, 5)


class TestKwargsUnwrapping(unittest.TestCase):
    """Tests for the kwargs wrapper unwrapping pattern."""

    def test_kwargs_wrapper_is_unwrapped(self):
        """Schemas wrapping args in a 'kwargs' field should be unwrapped."""
        schema = {
            'type': 'object',
            'properties': {
                'kwargs': {
                    'type': 'object',
                    'properties': {
                        'city': {'type': 'string'},
                        'units': {'type': 'string'},
                    },
                    'required': ['city'],
                }
            },
        }
        Model = create_pydantic_model_from_schema(schema, 'KwargsModel')
        instance = Model(city='Seattle')
        self.assertEqual(instance.city, 'Seattle')
        self.assertIsNone(instance.units)

    def test_non_kwargs_not_unwrapped(self):
        """Schemas without the kwargs wrapper should not be affected."""
        schema = {
            'type': 'object',
            'properties': {
                'city': {'type': 'string'},
            },
            'required': ['city'],
        }
        Model = create_pydantic_model_from_schema(schema, 'FlatModel')
        instance = Model(city='Tokyo')
        self.assertEqual(instance.city, 'Tokyo')


class TestEmptyAndEdgeCases(unittest.TestCase):
    """Tests for edge cases."""

    def test_empty_properties(self):
        schema = {'type': 'object', 'properties': {}}
        Model = create_pydantic_model_from_schema(schema, 'EmptyModel')
        instance = Model()
        self.assertIsInstance(instance, BaseModel)

    def test_no_properties_key(self):
        schema = {'type': 'object'}
        Model = create_pydantic_model_from_schema(schema, 'NoPropsModel')
        instance = Model()
        self.assertIsInstance(instance, BaseModel)

    def test_description_preserved(self):
        schema = {
            'type': 'object',
            'properties': {
                'city': {
                    'type': 'string',
                    'description': 'The city to query',
                }
            },
            'required': ['city'],
        }
        Model = create_pydantic_model_from_schema(schema, 'DescModel')
        field_info = Model.model_fields['city']
        self.assertEqual(field_info.description, 'The city to query')

    def test_returns_pydantic_model_subclass(self):
        schema = {
            'type': 'object',
            'properties': {'x': {'type': 'integer'}},
            'required': ['x'],
        }
        Model = create_pydantic_model_from_schema(schema, 'SubclassCheck')
        self.assertTrue(issubclass(Model, BaseModel))

    def test_model_name_set(self):
        schema = {
            'type': 'object',
            'properties': {'x': {'type': 'integer'}},
            'required': ['x'],
        }
        Model = create_pydantic_model_from_schema(schema, 'MyToolArgs')
        self.assertEqual(Model.__name__, 'MyToolArgs')


if __name__ == '__main__':
    unittest.main()
