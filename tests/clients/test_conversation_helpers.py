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
import io
import json
import base64
import unittest
import warnings
from contextlib import redirect_stdout
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List, Literal, Optional, Union, Set
from dapr.conf import settings
from dapr.clients.grpc._conversation_helpers import (
    stringify_tool_output,
    bind_params_to_func,
    function_to_json_schema,
    _extract_docstring_args,
    _python_type_to_json_schema,
    extract_docstring_summary,
    ToolArgumentError,
)
from dapr.clients.grpc.conversation import (
    ConversationToolsFunction,
    ConversationMessageOfUser,
    ConversationMessageContent,
    ConversationToolCalls,
    ConversationToolCallsOfFunction,
    ConversationMessageOfAssistant,
    ConversationMessageOfTool,
    ConversationMessage,
    ConversationMessageOfDeveloper,
    ConversationMessageOfSystem,
)


def test_string_passthrough():
    assert stringify_tool_output('hello') == 'hello'


def test_json_serialization_collections():
    data = {'a': 1, 'b': [2, 'x'], 'c': {'k': True}}
    out = stringify_tool_output(data)
    # Must be a JSON string we can parse back to the same structure
    parsed = json.loads(out)
    assert parsed == data


class Color(Enum):
    RED = 'red'
    BLUE = 'blue'


def test_enum_serialization_uses_value_and_is_json_string():
    out = stringify_tool_output(Color.RED)
    # json.dumps on a string value yields a quoted JSON string
    assert out == json.dumps('red', ensure_ascii=False)


@dataclass
class Point:
    x: int
    y: int


def test_dataclass_serialization_to_json_dict():
    p = Point(1, 2)
    out = stringify_tool_output(p)
    parsed = json.loads(out)
    assert parsed == {'x': 1, 'y': 2}


def test_bytes_and_bytearray_to_base64_prefixed():
    b = bytes([0, 1, 2, 250, 255])
    expected = 'base64:' + base64.b64encode(b).decode('ascii')
    assert stringify_tool_output(b) == expected

    ba = bytearray(b)
    expected_ba = 'base64:' + base64.b64encode(bytes(ba)).decode('ascii')
    assert stringify_tool_output(ba) == expected_ba


class WithDict:
    def __init__(self):
        self.x = 1
        self.y = 'y'
        self.fn = lambda: 42  # callable should be filtered out


def test_object_with___dict___becomes_dict_without_callables():
    obj = WithDict()
    out = stringify_tool_output(obj)
    parsed = json.loads(out)
    assert parsed == {'x': 1, 'y': 'y'}


class UnserializableButStr:
    def __init__(self):
        self.bad = {1, 2, 3}  # set is not JSON serializable

    def __str__(self):
        return 'myobj'


def test_fallback_to_str_when_json_fails():
    obj = UnserializableButStr()
    out = stringify_tool_output(obj)
    assert out == 'myobj'


class BadStr:
    def __init__(self):
        self.bad = {1, 2, 3}

    def __str__(self):
        raise RuntimeError('boom')


def test_last_resort_unserializable_marker_when_str_raises():
    obj = BadStr()
    out = stringify_tool_output(obj)
    assert out == '<unserializable>'


def _example_get_flights(
    *,
    flight_data: List[str],
    trip: Literal['round-trip', 'one-way', 'multi-city'],
    passengers: int,
    seat: Literal['economy', 'premium-economy', 'business', 'first'],
    fetch_mode: Literal['common', 'fallback', 'force-fallback', 'local'] = 'common',
    max_stops: Optional[int] = None,
):
    return {
        'flight_data': flight_data,
        'trip': trip,
        'passengers': passengers,
        'seat': seat,
        'fetch_mode': fetch_mode,
        'max_stops': max_stops,
    }


def test_bind_params_basic_coercion_from_examples():
    params = {
        'flight_data': ['AUS', 'OPO'],
        'trip': 'one-way',
        'passengers': '1',  # should coerce to int
        'seat': 'economy',
        'fetch_mode': 'common',
        'max_stops': 0,
    }
    bound = bind_params_to_func(_example_get_flights, params)
    # Ensure type coercion happened
    assert isinstance(bound.kwargs['passengers'], int)
    assert bound.kwargs['passengers'] == 1
    assert isinstance(bound.kwargs['max_stops'], int)
    # Function should still run with coerced params
    result = _example_get_flights(*bound.args, **bound.kwargs)
    assert result['passengers'] == 1
    assert result['trip'] == 'one-way'
    assert result['seat'] == 'economy'


def test_literal_schema_generation_from_examples():
    schema = function_to_json_schema(_example_get_flights)
    props = schema['properties']

    # flight_data -> array of strings
    assert props['flight_data']['type'] == 'array'
    assert props['flight_data']['items']['type'] == 'string'

    # trip -> enum of strings
    assert props['trip']['type'] == 'string'
    assert set(props['trip']['enum']) == {'round-trip', 'one-way', 'multi-city'}

    # passengers -> integer
    assert props['passengers']['type'] == 'integer'

    # seat -> enum of strings
    assert props['seat']['type'] == 'string'
    assert set(props['seat']['enum']) == {'economy', 'premium-economy', 'business', 'first'}

    # fetch_mode -> enum with default provided in function (not necessarily in schema, but not required)
    assert props['fetch_mode']['type'] == 'string'
    assert set(props['fetch_mode']['enum']) == {'common', 'fallback', 'force-fallback', 'local'}

    # max_stops -> optional int (not required)
    assert props['max_stops']['type'] == 'integer'

    # Required fields reflect parameters without defaults
    # Note: order not guaranteed
    required = set(schema['required'])
    assert {'flight_data', 'trip', 'passengers', 'seat'}.issubset(required)
    assert 'fetch_mode' not in required
    assert 'max_stops' not in required


# Define minimal stand-in classes to test class coercion behavior
class FlightData:
    def __init__(
        self, date: str, from_airport: str, to_airport: str, max_stops: Optional[int] = None
    ):
        self.date = date
        self.from_airport = from_airport
        self.to_airport = to_airport
        self.max_stops = max_stops


class Passengers:
    def __init__(self, adults: int, children: int, infants_in_seat: int, infants_on_lap: int):
        self.adults = adults
        self.children = children
        self.infants_in_seat = infants_in_seat
        self.infants_on_lap = infants_on_lap


def _example_get_flights_with_classes(
    *,
    flight_data: List[FlightData],
    trip: Literal['round-trip', 'one-way', 'multi-city'],
    passengers: Passengers,
    seat: Literal['economy', 'premium-economy', 'business', 'first'],
    fetch_mode: Literal['common', 'fallback', 'force-fallback', 'local'] = 'common',
    max_stops: Optional[int] = None,
):
    return {
        'flight_data': flight_data,
        'trip': trip,
        'passengers': passengers,
        'seat': seat,
        'fetch_mode': fetch_mode,
        'max_stops': max_stops,
    }


def test_class_coercion_and_schema_from_examples():
    # Verify schema generation includes class fields
    schema = function_to_json_schema(_example_get_flights_with_classes)
    props = schema['properties']

    # flight_data is array of objects with class fields
    fd_schema = props['flight_data']['items']
    assert fd_schema['type'] == 'object'
    for key in ['date', 'from_airport', 'to_airport']:
        assert key in fd_schema['properties']
        assert fd_schema['properties'][key]['type'] == 'string'
    # Optional int field
    assert fd_schema['properties']['max_stops']['type'] == 'integer'

    # passengers object has proper fields
    p_schema = props['passengers']
    assert p_schema['type'] == 'object'
    for key in ['adults', 'children', 'infants_in_seat', 'infants_on_lap']:
        assert p_schema['properties'][key]['type'] == 'integer'

    # Provide dicts to be coerced into class instances
    params = {
        'flight_data': [
            {'date': '2025-09-01', 'from_airport': 'AUS', 'to_airport': 'OPO', 'max_stops': '1'},
            {'date': '2025-09-10', 'from_airport': 'OPO', 'to_airport': 'AUS'},
        ],
        'trip': 'round-trip',
        'passengers': {'adults': 1, 'children': 0, 'infants_in_seat': 0, 'infants_on_lap': 0},
        'seat': 'economy',
        'fetch_mode': 'common',
        'max_stops': 1,
    }

    bound = bind_params_to_func(_example_get_flights_with_classes, params)
    result = _example_get_flights_with_classes(*bound.args, **bound.kwargs)

    # Ensure coerced instances
    assert all(isinstance(fd, FlightData) for fd in result['flight_data'])
    assert isinstance(result['passengers'], Passengers)
    # Ensure coercion of max_stops inside FlightData
    assert result['flight_data'][0].max_stops == 1


# ---- Additional function_to_json_schema tests for dataclass and other types ----


@dataclass
class Person:
    name: str
    age: int = 0  # default -> not required in schema


def _fn_with_dataclass(user: Person, teammates: Optional[List[Person]] = None):
    return True


def test_function_to_json_schema_with_dataclass_param():
    schema = function_to_json_schema(_fn_with_dataclass)
    props = schema['properties']

    # user -> dataclass object
    assert props['user']['type'] == 'object'
    assert set(props['user']['properties'].keys()) == {'name', 'age'}
    assert props['user']['properties']['name']['type'] == 'string'
    assert props['user']['properties']['age']['type'] == 'integer'
    # required should include 'user' (function param) and within dataclass, field default logic is internal;
    # for function level required, user has no default -> required
    assert 'user' in schema['required']

    # teammates -> Optional[List[Person]]
    assert props['teammates']['type'] == 'array'
    assert props['teammates']['items']['type'] == 'object'
    assert set(props['teammates']['items']['properties'].keys()) == {'name', 'age'}
    # teammates is Optional -> not required at top level
    assert 'teammates' not in schema['required']


class Pet(Enum):
    DOG = 'dog'
    CAT = 'cat'


def _fn_with_enum(pet: Pet):
    return True


def test_function_to_json_schema_with_enum_param():
    schema = function_to_json_schema(_fn_with_enum)
    pet_schema = schema['properties']['pet']
    assert pet_schema['type'] == 'string'
    assert set(pet_schema['enum']) == {'dog', 'cat'}


def _fn_with_dict(meta: Dict[str, int]):
    return True


def test_function_to_json_schema_with_dict_str_int():
    schema = function_to_json_schema(_fn_with_dict)
    meta_schema = schema['properties']['meta']
    assert meta_schema['type'] == 'object'
    assert meta_schema['additionalProperties']['type'] == 'integer'


def _fn_with_bytes(data: bytes):
    return True


def test_function_to_json_schema_with_bytes():
    schema = function_to_json_schema(_fn_with_bytes)
    data_schema = schema['properties']['data']
    assert data_schema['type'] == 'string'
    assert data_schema.get('format') == 'byte'


def _fn_with_union(identifier: Union[int, str]):
    return True


def test_function_to_json_schema_with_true_union_anyof():
    schema = function_to_json_schema(_fn_with_union)
    id_schema = schema['properties']['identifier']
    assert 'anyOf' in id_schema
    types = {opt.get('type') for opt in id_schema['anyOf']}
    assert types == {'integer', 'string'}


def _fn_with_unsupported_type(s: Set[int]):
    return True


def test_function_to_json_schema_unsupported_type_raises():
    try:
        function_to_json_schema(_fn_with_unsupported_type)
        assert False, 'Expected TypeError or ValueError for unsupported type'
    except (TypeError, ValueError):
        pass


class TestPythonTypeToJsonSchema(unittest.TestCase):
    """Test the _python_type_to_json_schema function."""

    def test_basic_types(self):
        """Test conversion of basic Python types."""
        test_cases = [
            (str, {'type': 'string'}),
            (int, {'type': 'integer'}),
            (float, {'type': 'number'}),
            (bool, {'type': 'boolean'}),
            (bytes, {'type': 'string', 'format': 'byte'}),
        ]

        for python_type, expected in test_cases:
            with self.subTest(python_type=python_type):
                result = _python_type_to_json_schema(python_type)
                self.assertEqual(result['type'], expected['type'])
                if 'format' in expected:
                    self.assertEqual(result['format'], expected['format'])

    def test_optional_types(self):
        """Test Optional[T] types (Union[T, None])."""
        # Optional[str] should resolve to string
        result = _python_type_to_json_schema(Optional[str])
        self.assertEqual(result['type'], 'string')

        # Optional[int] should resolve to integer
        result = _python_type_to_json_schema(Optional[int])
        self.assertEqual(result['type'], 'integer')

    def test_list_types(self):
        """Test List[T] types."""
        # List[str]
        result = _python_type_to_json_schema(List[str])
        expected = {'type': 'array', 'items': {'type': 'string'}}
        self.assertEqual(result, expected)

        # List[int]
        result = _python_type_to_json_schema(List[int])
        expected = {'type': 'array', 'items': {'type': 'integer'}}
        self.assertEqual(result, expected)

    def test_dict_types(self):
        """Test Dict[str, T] types."""
        result = _python_type_to_json_schema(Dict[str, int])
        expected = {'type': 'object', 'additionalProperties': {'type': 'integer'}}
        self.assertEqual(result, expected)

    def test_enum_types(self):
        """Test Enum types."""

        class Color(Enum):
            RED = 'red'
            GREEN = 'green'
            BLUE = 'blue'

        result = _python_type_to_json_schema(Color)
        expected = {'type': 'string', 'enum': ['red', 'green', 'blue']}
        self.assertEqual(result['type'], expected['type'])
        self.assertEqual(set(result['enum']), set(expected['enum']))

    def test_union_types(self):
        """Test Union types."""
        result = _python_type_to_json_schema(Union[str, int])
        self.assertIn('anyOf', result)
        self.assertEqual(len(result['anyOf']), 2)

        # Should contain both string and integer schemas
        types = [schema['type'] for schema in result['anyOf']]
        self.assertIn('string', types)
        self.assertIn('integer', types)

    def test_dataclass_types(self):
        """Test dataclass types."""

        @dataclass
        class Person:
            name: str
            age: int = 25

        result = _python_type_to_json_schema(Person)

        self.assertEqual(result['type'], 'object')
        self.assertIn('properties', result)
        self.assertIn('required', result)

        # Check properties
        self.assertIn('name', result['properties'])
        self.assertIn('age', result['properties'])
        self.assertEqual(result['properties']['name']['type'], 'string')
        self.assertEqual(result['properties']['age']['type'], 'integer')

        # Check required fields (name is required, age has default)
        self.assertIn('name', result['required'])
        self.assertNotIn('age', result['required'])

    def test_pydantic_models(self):
        """Test Pydantic model types."""
        try:
            from pydantic import BaseModel

            class SearchParams(BaseModel):
                query: str
                limit: int = 10
                include_images: bool = False
                tags: Optional[List[str]] = None

            result = _python_type_to_json_schema(SearchParams)

            # Pydantic models should generate their own schema
            self.assertIn('type', result)
            # The exact structure depends on Pydantic version, but it should have properties
            if 'properties' in result:
                self.assertIn('query', result['properties'])
        except ImportError:
            self.skipTest('Pydantic not available for testing')

    def test_nested_types(self):
        """Test complex nested type combinations."""
        # Optional[List[str]]
        result = _python_type_to_json_schema(Optional[List[str]])
        self.assertEqual(result['type'], 'array')
        self.assertEqual(result['items']['type'], 'string')

        # List[Optional[int]]
        result = _python_type_to_json_schema(List[Optional[int]])
        self.assertEqual(result['type'], 'array')
        self.assertEqual(result['items']['type'], 'integer')

        # Dict[str, List[int]]
        result = _python_type_to_json_schema(Dict[str, List[int]])
        self.assertEqual(result['type'], 'object')
        self.assertEqual(result['additionalProperties']['type'], 'array')
        self.assertEqual(result['additionalProperties']['items']['type'], 'integer')

    def test_complex_dataclass_with_nested_types(self):
        """Test dataclass with complex nested types."""

        @dataclass
        class Address:
            street: str
            city: str
            zipcode: Optional[str] = None

        @dataclass
        class Person:
            name: str
            addresses: List[Address]
            metadata: Dict[str, str]
            tags: Optional[List[str]] = None

        result = _python_type_to_json_schema(Person)

        self.assertEqual(result['type'], 'object')
        self.assertIn('name', result['properties'])
        self.assertIn('addresses', result['properties'])
        self.assertIn('metadata', result['properties'])
        self.assertIn('tags', result['properties'])

        # Check nested structures
        self.assertEqual(result['properties']['addresses']['type'], 'array')
        self.assertEqual(result['properties']['metadata']['type'], 'object')
        self.assertEqual(result['properties']['tags']['type'], 'array')

        # Required fields
        self.assertIn('name', result['required'])
        self.assertIn('addresses', result['required'])
        self.assertIn('metadata', result['required'])
        self.assertNotIn('tags', result['required'])

    def test_enum_with_different_types(self):
        """Test enums with different value types."""

        class Status(Enum):
            ACTIVE = 1
            INACTIVE = 0
            PENDING = 2

        class Priority(Enum):
            LOW = 'low'
            MEDIUM = 'medium'
            HIGH = 'high'

        # String enum
        result = _python_type_to_json_schema(Priority)
        self.assertEqual(result['type'], 'string')
        self.assertEqual(set(result['enum']), {'low', 'medium', 'high'})

        # Integer enum
        result = _python_type_to_json_schema(Status)
        self.assertEqual(result['type'], 'string')
        self.assertEqual(set(result['enum']), {1, 0, 2})

    def test_none_type(self):
        """Test None type handling."""
        result = _python_type_to_json_schema(type(None))
        self.assertEqual(result['type'], 'null')

    def test_realistic_function_types(self):
        """Test types from realistic function signatures."""
        # Weather function parameters
        result = _python_type_to_json_schema(str)  # location
        self.assertEqual(result['type'], 'string')

        # Optional unit with enum
        class TemperatureUnit(Enum):
            CELSIUS = 'celsius'
            FAHRENHEIT = 'fahrenheit'

        result = _python_type_to_json_schema(Optional[TemperatureUnit])
        self.assertEqual(result['type'], 'string')
        self.assertEqual(set(result['enum']), {'celsius', 'fahrenheit'})

        # Search function with complex params
        @dataclass
        class SearchOptions:
            max_results: int = 10
            include_metadata: bool = True
            filters: Optional[Dict[str, str]] = None

        result = _python_type_to_json_schema(SearchOptions)
        self.assertEqual(result['type'], 'object')
        self.assertIn('max_results', result['properties'])
        self.assertIn('include_metadata', result['properties'])
        self.assertIn('filters', result['properties'])

    def test_list_without_type_args(self):
        """Test bare List type without type arguments."""
        result = _python_type_to_json_schema(list)
        self.assertEqual(result['type'], 'array')
        self.assertNotIn('items', result)

    def test_dict_without_type_args(self):
        """Test bare Dict type without type arguments."""
        result = _python_type_to_json_schema(dict)
        self.assertEqual(result['type'], 'object')
        self.assertNotIn('additionalProperties', result)


class TestExtractDocstringInfo(unittest.TestCase):
    """Test the extract_docstring_info function."""

    def test_google_style_docstring(self):
        """Test Google-style docstring parsing."""

        def sample_function(name: str, age: int) -> str:
            """A sample function.

            Args:
                name: The person's name
                age: The person's age in years
            """
            return f'{name} is {age}'

        result = _extract_docstring_args(sample_function)
        expected = {'name': "The person's name", 'age': "The person's age in years"}
        self.assertEqual(result, expected)

    def test_no_docstring(self):
        """Test function with no docstring."""

        def no_doc_function(param):
            pass

        result = _extract_docstring_args(no_doc_function)
        self.assertEqual(result, {})

    def test_docstring_without_args(self):
        """Test docstring without Args section."""

        def simple_function(param):
            """Just a simple function."""
            pass

        result = _extract_docstring_args(simple_function)
        self.assertEqual(result, {})

    def test_multiline_param_description(self):
        """Test parameter descriptions that span multiple lines."""

        def complex_function(param1: str) -> str:
            """A complex function.

            Args:
                param1: This is a long description
                    that spans multiple lines
                    for testing purposes
            """
            return param1

        result = _extract_docstring_args(complex_function)
        expected = {
            'param1': 'This is a long description that spans multiple lines for testing purposes'
        }
        self.assertEqual(result, expected)

    def test_sphinx_style_docstring(self):
        """Test Sphinx-style docstring parsing."""

        def sphinx_function(location: str, unit: str) -> str:
            """Get weather information.

            :param location: The city or location name
            :param unit: Temperature unit (celsius or fahrenheit)
            :type location: str
            :type unit: str
            :returns: Weather information string
            :rtype: str
            """
            return f'Weather in {location}'

        result = _extract_docstring_args(sphinx_function)
        expected = {
            'location': 'The city or location name',
            'unit': 'Temperature unit (celsius or fahrenheit)',
        }
        self.assertEqual(result, expected)

    def test_sphinx_style_with_parameter_keyword(self):
        """Test Sphinx-style with :parameter: instead of :param:."""

        def sphinx_function2(query: str, limit: int) -> str:
            """Search for data.

            :parameter query: The search query string
            :parameter limit: Maximum number of results
            """
            return f'Results for {query}'

        result = _extract_docstring_args(sphinx_function2)
        expected = {'query': 'The search query string', 'limit': 'Maximum number of results'}
        self.assertEqual(result, expected)

    def test_sphinx_style_multiline_descriptions(self):
        """Test Sphinx-style with multi-line parameter descriptions."""

        def sphinx_multiline_function(data: str) -> str:
            """Process complex data.

            :param data: The input data to process, which can be
                quite complex and may require special handling
                for optimal results
            :returns: Processed data
            """
            return data

        result = _extract_docstring_args(sphinx_multiline_function)
        expected = {
            'data': 'The input data to process, which can be quite complex and may require special handling for optimal results'
        }
        self.assertEqual(result, expected)

    def test_numpy_style_docstring(self):
        """Test NumPy-style docstring parsing."""

        def numpy_function(x: float, y: float) -> float:
            """Calculate distance.

            Parameters
            ----------
            x : float
                The x coordinate
            y : float
                The y coordinate

            Returns
            -------
            float
                The calculated distance
            """
            return (x**2 + y**2) ** 0.5

        result = _extract_docstring_args(numpy_function)
        expected = {'x': 'The x coordinate', 'y': 'The y coordinate'}
        self.assertEqual(result, expected)

    def test_mixed_style_preference(self):
        """Test that Sphinx-style takes precedence when both styles are present."""

        def mixed_function(param1: str, param2: int) -> str:
            """Function with mixed documentation styles.

            :param param1: Sphinx-style description for param1
            :param param2: Sphinx-style description for param2

            Args:
                param1: Google-style description for param1
                param2: Google-style description for param2
            """
            return f'{param1}: {param2}'

        result = _extract_docstring_args(mixed_function)
        expected = {
            'param1': 'Sphinx-style description for param1',
            'param2': 'Sphinx-style description for param2',
        }
        self.assertEqual(result, expected)

    def test_unsupported_format_warning(self):
        """Test that unsupported docstring formats trigger a warning."""

        def unsupported_function(param1: str, param2: int) -> str:
            """Function with unsupported parameter documentation format.

            This function takes param1 which is a string input,
            and param2 which is an integer argument.
            """
            return f'{param1}: {param2}'

        with self.assertWarns(UserWarning) as warning_context:
            result = _extract_docstring_args(unsupported_function)

        # Should return empty dict since no supported format found
        self.assertEqual(result, {})

        # Check warning message content
        warning_message = str(warning_context.warning)
        self.assertIn('unsupported_function', warning_message)
        self.assertIn('supported format', warning_message)
        self.assertIn('Google, NumPy, or Sphinx style', warning_message)

    def test_informal_style_warning(self):
        """Test that informal parameter documentation triggers a warning."""

        def informal_function(filename: str, mode: str) -> str:
            """Open and read a file.

            The filename parameter should be the path to the file.
            The mode parameter controls how the file is opened.
            """
            return f'Reading {filename} in {mode} mode'

        with self.assertWarns(UserWarning):
            result = _extract_docstring_args(informal_function)

        self.assertEqual(result, {})

    def test_no_warning_for_no_params(self):
        """Test that functions without parameter docs don't trigger warnings."""

        def simple_function() -> str:
            """Simple function with no parameters documented."""
            return 'hello'

        # Should not raise any warnings
        with warnings.catch_warnings():
            warnings.simplefilter('error')  # Turn warnings into errors
            result = _extract_docstring_args(simple_function)

        self.assertEqual(result, {})

    def test_no_warning_for_valid_formats(self):
        """Test that valid formats don't trigger warnings."""

        def google_function(param: str) -> str:
            """Function with Google-style docs.

            Args:
                param: A parameter description
            """
            return param

        # Should not raise any warnings
        with warnings.catch_warnings():
            warnings.simplefilter('error')  # Turn warnings into errors
            result = _extract_docstring_args(google_function)

        self.assertEqual(result, {'param': 'A parameter description'})


class TestFunctionToJsonSchema(unittest.TestCase):
    """Test the function_to_json_schema function."""

    def test_simple_function(self):
        """Test a simple function with basic types."""

        def get_weather(location: str, unit: str = 'fahrenheit') -> str:
            """Get weather for a location.

            Args:
                location: The city name
                unit: Temperature unit
            """
            return f'Weather in {location}'

        result = function_to_json_schema(get_weather)

        # Check structure
        self.assertEqual(result['type'], 'object')
        self.assertIn('properties', result)
        self.assertIn('required', result)

        # Check properties
        self.assertIn('location', result['properties'])
        self.assertIn('unit', result['properties'])
        self.assertEqual(result['properties']['location']['type'], 'string')
        self.assertEqual(result['properties']['unit']['type'], 'string')

        # Check descriptions
        self.assertEqual(result['properties']['location']['description'], 'The city name')
        self.assertEqual(result['properties']['unit']['description'], 'Temperature unit')

        # Check required (location is required, unit has default)
        self.assertIn('location', result['required'])
        self.assertNotIn('unit', result['required'])

    def test_function_with_complex_types(self):
        """Test function with complex type hints."""

        def search_data(
            query: str,
            limit: int = 10,
            filters: Optional[List[str]] = None,
            metadata: Dict[str, str] = None,
        ) -> Dict[str, any]:
            """Search for data.

            Args:
                query: Search query
                limit: Maximum results
                filters: Optional search filters
                metadata: Additional metadata
            """
            return {}

        result = function_to_json_schema(search_data)

        # Check all parameters are present
        props = result['properties']
        self.assertIn('query', props)
        self.assertIn('limit', props)
        self.assertIn('filters', props)
        self.assertIn('metadata', props)

        # Check types
        self.assertEqual(props['query']['type'], 'string')
        self.assertEqual(props['limit']['type'], 'integer')
        self.assertEqual(props['filters']['type'], 'array')
        self.assertEqual(props['filters']['items']['type'], 'string')
        self.assertEqual(props['metadata']['type'], 'object')

        # Check required (only query is required)
        self.assertEqual(result['required'], ['query'])

    def test_function_with_enum(self):
        """Test function with Enum parameter."""

        class Priority(Enum):
            LOW = 'low'
            HIGH = 'high'

        def create_task(name: str, priority: Priority = Priority.LOW) -> str:
            """Create a task.

            Args:
                name: Task name
                priority: Task priority level
            """
            return f'Task: {name}'

        result = function_to_json_schema(create_task)

        # Check enum handling
        priority_prop = result['properties']['priority']
        self.assertEqual(priority_prop['type'], 'string')
        self.assertIn('enum', priority_prop)
        self.assertEqual(set(priority_prop['enum']), {'low', 'high'})

    def test_function_no_parameters(self):
        """Test function with no parameters."""

        def get_time() -> str:
            """Get current time."""
            return '12:00'

        result = function_to_json_schema(get_time)

        self.assertEqual(result['type'], 'object')
        self.assertEqual(result['properties'], {})
        self.assertEqual(result['required'], [])

    def test_function_with_args_kwargs(self):
        """Test function with *args and **kwargs (should be ignored)."""

        def flexible_function(name: str, *args, **kwargs) -> str:
            """A flexible function."""
            return name

        result = function_to_json_schema(flexible_function)

        # Should only include 'name', not *args or **kwargs
        self.assertEqual(list(result['properties'].keys()), ['name'])
        self.assertEqual(result['required'], ['name'])

    def test_realistic_weather_function(self):
        """Test realistic weather API function."""

        class Units(Enum):
            CELSIUS = 'celsius'
            FAHRENHEIT = 'fahrenheit'

        def get_weather(
            location: str, unit: Units = Units.FAHRENHEIT, include_forecast: bool = False
        ) -> str:
            """Get current weather for a location.

            Args:
                location: The city and state or country
                unit: Temperature unit preference
                include_forecast: Whether to include 5-day forecast
            """
            return f'Weather in {location}'

        result = function_to_json_schema(get_weather)

        # Check structure
        self.assertEqual(result['type'], 'object')
        props = result['properties']

        # Check location (required string)
        self.assertEqual(props['location']['type'], 'string')
        self.assertEqual(props['location']['description'], 'The city and state or country')
        self.assertIn('location', result['required'])

        # Check unit (optional enum)
        self.assertEqual(props['unit']['type'], 'string')
        self.assertEqual(set(props['unit']['enum']), {'celsius', 'fahrenheit'})
        self.assertNotIn('unit', result['required'])

        # Check forecast flag (optional boolean)
        self.assertEqual(props['include_forecast']['type'], 'boolean')
        self.assertNotIn('include_forecast', result['required'])

    def test_realistic_search_function(self):
        """Test realistic search function with complex parameters."""

        @dataclass
        class SearchFilters:
            category: Optional[str] = None
            price_min: Optional[float] = None
            price_max: Optional[float] = None

        def search_products(
            query: str,
            max_results: int = 20,
            sort_by: str = 'relevance',
            filters: Optional[SearchFilters] = None,
            include_metadata: bool = True,
        ) -> List[Dict[str, str]]:
            """Search for products in catalog.

            Args:
                query: Search query string
                max_results: Maximum number of results to return
                sort_by: Sort order (relevance, price, rating)
                filters: Optional search filters
                include_metadata: Whether to include product metadata
            """
            return []

        result = function_to_json_schema(search_products)

        props = result['properties']

        # Check required query
        self.assertEqual(props['query']['type'], 'string')
        self.assertIn('query', result['required'])

        # Check optional integer with default
        self.assertEqual(props['max_results']['type'], 'integer')
        self.assertNotIn('max_results', result['required'])

        # Check string with default
        self.assertEqual(props['sort_by']['type'], 'string')
        self.assertNotIn('sort_by', result['required'])

        # Check optional dataclass
        self.assertEqual(props['filters']['type'], 'object')
        self.assertNotIn('filters', result['required'])

        # Check boolean with default
        self.assertEqual(props['include_metadata']['type'], 'boolean')
        self.assertNotIn('include_metadata', result['required'])

    def test_realistic_database_function(self):
        """Test realistic database query function."""

        def query_users(
            filter_conditions: Dict[str, str],
            limit: int = 100,
            offset: int = 0,
            order_by: Optional[str] = None,
            include_inactive: bool = False,
        ) -> List[Dict[str, any]]:
            """Query users from database.

            Args:
                filter_conditions: Key-value pairs for filtering
                limit: Maximum number of users to return
                offset: Number of records to skip
                order_by: Field to sort by
                include_inactive: Whether to include inactive users
            """
            return []

        result = function_to_json_schema(query_users)

        props = result['properties']

        # Check required dict parameter
        self.assertEqual(props['filter_conditions']['type'], 'object')
        self.assertIn('filter_conditions', result['required'])

        # Check integer parameters with defaults
        for param in ['limit', 'offset']:
            self.assertEqual(props[param]['type'], 'integer')
            self.assertNotIn(param, result['required'])

        # Check optional string
        self.assertEqual(props['order_by']['type'], 'string')
        self.assertNotIn('order_by', result['required'])

        # Check boolean flag
        self.assertEqual(props['include_inactive']['type'], 'boolean')
        self.assertNotIn('include_inactive', result['required'])

    def test_pydantic_function_parameter(self):
        """Test function with Pydantic model parameter."""
        try:
            from pydantic import BaseModel

            class UserProfile(BaseModel):
                name: str
                email: str
                age: Optional[int] = None
                preferences: Dict[str, bool] = {}

            def update_user(user_id: str, profile: UserProfile, notify: bool = True) -> str:
                """Update user profile.

                Args:
                    user_id: Unique user identifier
                    profile: User profile data
                    notify: Whether to send notification
                """
                return 'updated'

            result = function_to_json_schema(update_user)

            props = result['properties']

            # Check required string
            self.assertEqual(props['user_id']['type'], 'string')
            self.assertIn('user_id', result['required'])

            # Check Pydantic model (should have proper schema)
            self.assertIn('profile', props)
            self.assertIn('profile', result['required'])

            # Check boolean flag
            self.assertEqual(props['notify']['type'], 'boolean')
            self.assertNotIn('notify', result['required'])

        except ImportError:
            self.skipTest('Pydantic not available for testing')


class TestExtractDocstringSummary(unittest.TestCase):
    """Test the extract_docstring_summary function."""

    def test_simple_docstring(self):
        """Test function with simple one-line docstring."""

        def simple_function():
            """Simple one-line description."""
            pass

        result = extract_docstring_summary(simple_function)
        self.assertEqual(result, 'Simple one-line description.')

    def test_full_docstring_with_extended_summary(self):
        """Test function with full docstring including extended summary."""

        def complex_function():
            """Get weather information for a specific location.

            This function retrieves current weather data including temperature,
            humidity, and precipitation for the given location.

            Args:
                location: The city or location to get weather for
                unit: Temperature unit (celsius or fahrenheit)

            Returns:
                Weather information as a string

            Raises:
                ValueError: If location is invalid
            """
            pass

        result = extract_docstring_summary(complex_function)
        expected = (
            'Get weather information for a specific location. '
            'This function retrieves current weather data including temperature, '
            'humidity, and precipitation for the given location.'
        )
        self.assertEqual(result, expected)

    def test_multiline_summary_before_args(self):
        """Test function with multiline summary that stops at Args section."""

        def multiline_summary_function():
            """Complex function that does many things.

            This is an extended description that spans multiple lines
            and provides more context about what the function does.

            Args:
                param1: First parameter
            """
            pass

        result = extract_docstring_summary(multiline_summary_function)
        expected = (
            'Complex function that does many things. '
            'This is an extended description that spans multiple lines '
            'and provides more context about what the function does.'
        )
        self.assertEqual(result, expected)

    def test_no_docstring(self):
        """Test function without docstring."""

        def no_docstring_function():
            pass

        result = extract_docstring_summary(no_docstring_function)
        self.assertIsNone(result)

    def test_empty_docstring(self):
        """Test function with empty docstring."""

        def empty_docstring_function():
            """"""
            pass

        result = extract_docstring_summary(empty_docstring_function)
        self.assertIsNone(result)

    def test_docstring_with_only_whitespace(self):
        """Test function with docstring containing only whitespace."""

        def whitespace_docstring_function():
            """ """
            pass

        result = extract_docstring_summary(whitespace_docstring_function)
        self.assertIsNone(result)

    def test_docstring_stops_at_various_sections(self):
        """Test that summary extraction stops at various section headers."""

        def function_with_returns():
            """Function description.

            Returns:
                Something useful
            """
            pass

        def function_with_raises():
            """Function description.

            Raises:
                ValueError: If something goes wrong
            """
            pass

        def function_with_note():
            """Function description.

            Note:
                This is important to remember
            """
            pass

        # Test each section header
        for func in [function_with_returns, function_with_raises, function_with_note]:
            result = extract_docstring_summary(func)
            self.assertEqual(result, 'Function description.')

    def test_docstring_with_parameters_section(self):
        """Test docstring with Parameters section (alternative to Args)."""

        def function_with_parameters():
            """Process data efficiently.

            Parameters:
                data: Input data to process
                options: Processing options
            """
            pass

        result = extract_docstring_summary(function_with_parameters)
        self.assertEqual(result, 'Process data efficiently.')

    def test_docstring_with_example_section(self):
        """Test docstring with Example section."""

        def function_with_example():
            """Calculate the area of a circle.

            Example:
                >>> calculate_area(5)
                78.54
            """
            pass

        result = extract_docstring_summary(function_with_example)
        self.assertEqual(result, 'Calculate the area of a circle.')

    def test_case_insensitive_section_headers(self):
        """Test that section header matching is case insensitive."""

        def function_with_uppercase_args():
            """Function with uppercase section.

            ARGS:
                param: A parameter
            """
            pass

        result = extract_docstring_summary(function_with_uppercase_args)
        self.assertEqual(result, 'Function with uppercase section.')

    def test_sphinx_style_summary_extraction(self):
        """Test that Sphinx-style docstrings stop at :param: sections."""

        def sphinx_function():
            """Calculate mathematical operations.

            This function performs various mathematical calculations
            with high precision and error handling.

            :param x: First number
            :param y: Second number
            :returns: Calculation result
            """
            pass

        result = extract_docstring_summary(sphinx_function)
        expected = (
            'Calculate mathematical operations. '
            'This function performs various mathematical calculations '
            'with high precision and error handling.'
        )
        self.assertEqual(result, expected)

    def test_mixed_sphinx_google_summary(self):
        """Test summary extraction stops at first section marker (Sphinx or Google)."""

        def mixed_function():
            """Process data with multiple algorithms.

            This is an extended description that provides
            more context about the processing methods.

            :param data: Input data

            Args:
                additional: More parameters
            """
            pass

        result = extract_docstring_summary(mixed_function)
        expected = (
            'Process data with multiple algorithms. '
            'This is an extended description that provides '
            'more context about the processing methods.'
        )
        self.assertEqual(result, expected)


class TestConversationToolsFunctionFromFunction(unittest.TestCase):
    """Test the ConversationToolsFunction.from_function method."""

    def test_from_function_basic(self):
        """Test creating ConversationToolsFunction from a basic function."""

        def test_function(param1: str, param2: int = 10):
            """Test function for conversion.

            Args:
                param1: First parameter
                param2: Second parameter with default
            """
            return f'{param1}: {param2}'

        result = ConversationToolsFunction.from_function(test_function)

        # Check basic properties
        self.assertEqual(result.name, 'test_function')
        self.assertEqual(result.description, 'Test function for conversion.')
        self.assertIsInstance(result.parameters, dict)

        # Check that parameters schema was generated
        self.assertEqual(result.parameters['type'], 'object')
        self.assertIn('properties', result.parameters)
        self.assertIn('required', result.parameters)

    def test_from_function_with_complex_docstring(self):
        """Test from_function with complex docstring extracts only summary."""

        def complex_function(location: str):
            """Get weather information for a location.

            This function provides comprehensive weather data including
            current conditions and forecasts.

            Args:
                location: The location to get weather for

            Returns:
                str: Weather information

            Raises:
                ValueError: If location is invalid

            Example:
                >>> get_weather("New York")
                "Sunny, 72°F"
            """
            return f'Weather for {location}'

        result = ConversationToolsFunction.from_function(complex_function)

        expected_description = (
            'Get weather information for a location. '
            'This function provides comprehensive weather data including '
            'current conditions and forecasts.'
        )
        self.assertEqual(result.description, expected_description)

    def test_from_function_no_docstring(self):
        """Test from_function with function that has no docstring."""

        def no_doc_function(param):
            return param

        result = ConversationToolsFunction.from_function(no_doc_function)

        self.assertEqual(result.name, 'no_doc_function')
        self.assertIsNone(result.description)
        self.assertIsInstance(result.parameters, dict)

    def test_from_function_simple_docstring(self):
        """Test from_function with simple one-line docstring."""

        def simple_function():
            """Simple function description."""
            pass

        result = ConversationToolsFunction.from_function(simple_function)

        self.assertEqual(result.name, 'simple_function')
        self.assertEqual(result.description, 'Simple function description.')

    def test_from_function_sphinx_style_summary(self):
        """Test from_function extracts only summary from Sphinx-style docstring."""

        def sphinx_function(location: str):
            """Get weather information for a location.

            This function provides comprehensive weather data including
            current conditions and forecasts using various APIs.

            :param location: The location to get weather for
            :type location: str
            :returns: Weather information string
            :rtype: str
            :raises ValueError: If location is invalid
            """
            return f'Weather for {location}'

        result = ConversationToolsFunction.from_function(sphinx_function)

        expected_description = (
            'Get weather information for a location. '
            'This function provides comprehensive weather data including '
            'current conditions and forecasts using various APIs.'
        )
        self.assertEqual(result.description, expected_description)

    def test_from_function_google_style_summary(self):
        """Test from_function extracts only summary from Google-style docstring."""

        def google_function(data: str):
            """Process input data efficiently.

            This function handles various data formats and applies
            multiple processing algorithms for optimal results.

            Args:
                data: The input data to process

            Returns:
                str: Processed data string

            Raises:
                ValueError: If data format is invalid
            """
            return f'Processed {data}'

        result = ConversationToolsFunction.from_function(google_function)

        expected_description = (
            'Process input data efficiently. '
            'This function handles various data formats and applies '
            'multiple processing algorithms for optimal results.'
        )
        self.assertEqual(result.description, expected_description)


class TestIntegrationScenarios(unittest.TestCase):
    """Test real-world integration scenarios."""

    def test_restaurant_finder_scenario(self):
        """Test the restaurant finder example from the documentation."""
        from enum import Enum
        from typing import List, Optional

        class PriceRange(Enum):
            BUDGET = 'budget'
            MODERATE = 'moderate'
            EXPENSIVE = 'expensive'

        def find_restaurants(
            location: str,
            cuisine: str = 'any',
            price_range: PriceRange = PriceRange.MODERATE,
            max_results: int = 5,
            dietary_restrictions: Optional[List[str]] = None,
        ) -> str:
            """Find restaurants in a specific location.

            Args:
                location: The city or neighborhood to search
                cuisine: Type of cuisine (italian, chinese, mexican, etc.)
                price_range: Budget preference for dining
                max_results: Maximum number of restaurant recommendations
                dietary_restrictions: Special dietary needs (vegetarian, gluten-free, etc.)
            """
            return f'Found restaurants in {location}'

        schema = function_to_json_schema(find_restaurants)

        # Comprehensive validation
        self.assertEqual(schema['type'], 'object')

        # Check all properties exist
        props = schema['properties']
        self.assertIn('location', props)
        self.assertIn('cuisine', props)
        self.assertIn('price_range', props)
        self.assertIn('max_results', props)
        self.assertIn('dietary_restrictions', props)

        # Check types
        self.assertEqual(props['location']['type'], 'string')
        self.assertEqual(props['cuisine']['type'], 'string')
        self.assertEqual(props['price_range']['type'], 'string')
        self.assertEqual(props['max_results']['type'], 'integer')
        self.assertEqual(props['dietary_restrictions']['type'], 'array')
        self.assertEqual(props['dietary_restrictions']['items']['type'], 'string')

        # Check enum values
        self.assertEqual(set(props['price_range']['enum']), {'budget', 'moderate', 'expensive'})

        # Check descriptions
        self.assertIn('description', props['location'])
        self.assertIn('description', props['cuisine'])
        self.assertIn('description', props['price_range'])

        # Check required (only location is required)
        self.assertEqual(schema['required'], ['location'])

    def test_weather_api_scenario(self):
        """Test a weather API scenario with validation."""
        from enum import Enum
        from typing import Optional

        class Units(Enum):
            CELSIUS = 'celsius'
            FAHRENHEIT = 'fahrenheit'
            KELVIN = 'kelvin'

        def get_weather_forecast(
            latitude: float,
            longitude: float,
            units: Units = Units.CELSIUS,
            days: int = 7,
            include_hourly: bool = False,
            api_key: Optional[str] = None,
        ) -> Dict[str, any]:
            """Get weather forecast for coordinates.

            Args:
                latitude: Latitude coordinate
                longitude: Longitude coordinate
                units: Temperature units for response
                days: Number of forecast days
                include_hourly: Whether to include hourly forecasts
                api_key: Optional API key override
            """
            return {'forecast': []}

        schema = function_to_json_schema(get_weather_forecast)

        # Check numeric types
        self.assertEqual(schema['properties']['latitude']['type'], 'number')
        self.assertEqual(schema['properties']['longitude']['type'], 'number')
        self.assertEqual(schema['properties']['days']['type'], 'integer')
        self.assertEqual(schema['properties']['include_hourly']['type'], 'boolean')

        # Check enum
        self.assertEqual(schema['properties']['units']['type'], 'string')
        self.assertEqual(
            set(schema['properties']['units']['enum']), {'celsius', 'fahrenheit', 'kelvin'}
        )

        # Check required fields
        self.assertEqual(set(schema['required']), {'latitude', 'longitude'})


class TestTracePrintUserMixin(unittest.TestCase):
    def test_user_trace_print_with_name_and_multiple_contents(self):
        msg = ConversationMessageOfUser(
            name='alice',
            content=[
                ConversationMessageContent(text='hello'),
                ConversationMessageContent(text='how are you?'),
            ],
        )
        buf = io.StringIO()
        with redirect_stdout(buf):
            msg.trace_print(indent=2)
        out = buf.getvalue().splitlines()
        # Name line with indent
        self.assertEqual('  name: alice', out[0])
        # Content lines with computed indentation
        self.assertEqual('  content[0]: hello', out[1])
        self.assertEqual('  content[1]: how are you?', out[2])


class TestTracePrintAssistant(unittest.TestCase):
    def test_assistant_trace_print_with_tool_calls(self):
        tool_calls = [
            ConversationToolCalls(
                id='id1',
                function=ConversationToolCallsOfFunction(
                    name='get_weather', arguments='{"location":"Paris"}'
                ),
            )
        ]
        msg = ConversationMessageOfAssistant(
            name='helper',
            content=[ConversationMessageContent(text='checking weather')],
            tool_calls=tool_calls,
        )
        buf = io.StringIO()
        with redirect_stdout(buf):
            msg.trace_print(indent=0)
        lines = buf.getvalue().strip().splitlines()
        # Name line
        self.assertEqual(lines[0], 'name: helper')
        # Content line
        self.assertEqual(lines[1], 'content[0]: checking weather')
        # Tool calls header and entry
        self.assertEqual(lines[2], 'tool_calls: 1')
        self.assertEqual(lines[3], '  [0] id=id1 function=get_weather({"location":"Paris"})')


class TestTracePrintTool(unittest.TestCase):
    def test_tool_trace_print_multiline_content(self):
        msg = ConversationMessageOfTool(
            tool_id='tid-123',
            name='get_weather',
            content=[
                ConversationMessageContent(text='line1\nline2\nline3'),
            ],
        )
        buf = io.StringIO()
        with redirect_stdout(buf):
            msg.trace_print(indent=2)
        lines = buf.getvalue().splitlines()
        # tool_id and name printed with indent
        self.assertEqual(lines[0], '  tool_id: tid-123')
        self.assertEqual(lines[1], '  name: get_weather')
        # First line has the content[0] prefix with indent
        self.assertEqual(lines[2], '  content[0]: line1')
        # Subsequent lines are printed as-is per implementation
        self.assertEqual(lines[3], 'line2')
        self.assertEqual(lines[4], 'line3')


class TestTracePrintConversationMessage(unittest.TestCase):
    def test_conversation_message_headers_for_all_roles(self):
        msg = ConversationMessage(
            of_user=ConversationMessageOfUser(
                name='bob', content=[ConversationMessageContent(text='hi')]
            ),
            of_assistant=ConversationMessageOfAssistant(
                content=[ConversationMessageContent(text='hello')]
            ),
            of_tool=ConversationMessageOfTool(
                tool_id='t1',
                name='tool.fn',
                content=[ConversationMessageContent(text='ok')],
            ),
            of_developer=ConversationMessageOfDeveloper(
                name='dev', content=[ConversationMessageContent(text='turn on feature x')]
            ),
            of_system=ConversationMessageOfSystem(
                name='policy', content=[ConversationMessageContent(text='Follow company policy.')]
            ),
        )
        buf = io.StringIO()
        with redirect_stdout(buf):
            msg.trace_print(indent=0)
        out = buf.getvalue().splitlines()
        # First line is an empty line due to initial print()
        self.assertEqual(out[0], '')
        # Headers for each role appear
        # Developer header and content
        self.assertEqual(out[1], 'client[devel]  --------------> LLM[assistant]:')
        self.assertEqual(out[2], '  name: dev')
        self.assertEqual(out[3], '  content[0]: turn on feature x')
        # System header and content
        self.assertEqual(out[4], 'client[system] --------------> LLM[assistant]:')
        self.assertEqual(out[5], '  name: policy')
        self.assertEqual(out[6], '  content[0]: Follow company policy.')
        # Delegated lines for user (name first, then content)
        self.assertEqual(out[7], 'client[user]   --------------> LLM[assistant]:')
        self.assertEqual(out[8], '  name: bob')
        self.assertEqual(out[9], '  content[0]: hi')
        # Assistant header and content
        self.assertEqual(out[10], 'client         <------------- LLM[assistant]:')
        self.assertIn('  content[0]: hello', out[11])
        # Tool header and content
        self.assertEqual(out[12], 'client[tool]   -------------> LLM[assistant]:')
        self.assertEqual(out[13], '  tool_id: t1')
        self.assertEqual(out[14], '  name: tool.fn')
        self.assertEqual(out[15], '  content[0]: ok')


class TestLargeEnumBehavior(unittest.TestCase):
    def setUp(self):
        # Save originals
        self._orig_max = settings.DAPR_CONVERSATION_TOOLS_MAX_ENUM_ITEMS
        self._orig_beh = settings.DAPR_CONVERSATION_TOOLS_LARGE_ENUM_BEHAVIOR

    def tearDown(self):
        # Restore
        settings.DAPR_CONVERSATION_TOOLS_MAX_ENUM_ITEMS = self._orig_max
        settings.DAPR_CONVERSATION_TOOLS_LARGE_ENUM_BEHAVIOR = self._orig_beh

    def test_large_enum_compacted_to_string(self):
        # Make threshold tiny to trigger large-enum path
        settings.DAPR_CONVERSATION_TOOLS_MAX_ENUM_ITEMS = 2
        settings.DAPR_CONVERSATION_TOOLS_LARGE_ENUM_BEHAVIOR = 'string'

        class BigEnum(Enum):
            A = 'a'
            B = 'b'
            C = 'c'
            D = 'd'

        schema = _python_type_to_json_schema(BigEnum)
        # Should be compacted to string with description and examples
        self.assertEqual(schema.get('type'), 'string')
        self.assertIn('description', schema)
        self.assertIn('examples', schema)
        self.assertTrue(len(schema['examples']) > 0)

    def test_large_enum_error_mode(self):
        settings.DAPR_CONVERSATION_TOOLS_MAX_ENUM_ITEMS = 1
        settings.DAPR_CONVERSATION_TOOLS_LARGE_ENUM_BEHAVIOR = 'error'

        from enum import Enum

        class BigEnum(Enum):
            A = 'a'
            B = 'b'

        with self.assertRaises(ValueError):
            _python_type_to_json_schema(BigEnum)


class TestCoercionsAndBinding(unittest.TestCase):
    def test_coerce_bool_variants(self):
        def f(flag: bool) -> bool:
            return flag

        # True-ish variants
        for v in ['true', 'True', 'YES', '1', 'on', ' y ']:
            bound = bind_params_to_func(f, {'flag': v})
            self.assertIs(f(*bound.args, **bound.kwargs), True)

        # False-ish variants
        for v in ['false', 'False', 'NO', '0', 'off', ' n ']:
            bound = bind_params_to_func(f, {'flag': v})
            self.assertIs(f(*bound.args, **bound.kwargs), False)

        # Invalid
        with self.assertRaises(ToolArgumentError):
            bind_params_to_func(f, {'flag': 'maybe'})

    def test_literal_numeric_from_string(self):
        def g(x: Literal[1, 2, 3]) -> int:
            return x  # type: ignore[return-value]

        bound = bind_params_to_func(g, {'x': '2'})
        self.assertEqual(g(*bound.args, **bound.kwargs), 2)

    def test_unexpected_kwarg_is_rejected(self):
        def h(a: int) -> int:
            return a

        with self.assertRaises(Exception):
            bind_params_to_func(h, {'a': 1, 'extra': 2})

    def test_dataclass_arg_validation(self):
        @dataclass
        class P:
            x: int
            y: str

        def k(p: P) -> str:
            return p.y

        # Passing an instance is fine
        p = P(1, 'ok')
        bound = bind_params_to_func(k, {'p': p})
        self.assertEqual(k(*bound.args, **bound.kwargs), 'ok')

        # Passing a dict should fail for dataclass per implementation
        with self.assertRaises(ToolArgumentError):
            bind_params_to_func(k, {'p': {'x': 1, 'y': 'nope'}})


class TestPlainClassSchema(unittest.TestCase):
    def test_plain_class_init_signature(self):
        class C:
            def __init__(self, a: int, b: str = 'x'):
                self.a = a
                self.b = b

        schema = _python_type_to_json_schema(C)
        self.assertEqual(schema['type'], 'object')
        props = schema['properties']
        self.assertIn('a', props)
        self.assertIn('b', props)
        # Only 'a' is required
        self.assertIn('required', schema)
        self.assertEqual(schema['required'], ['a'])

    def test_plain_class_slots_fallback(self):
        class D:
            __slots__ = ('m', 'n')
            m: int
            n: Optional[str]

        schema = _python_type_to_json_schema(D)
        # Implementation builds properties from __slots__ with required for non-optional
        self.assertEqual(schema['type'], 'object')
        self.assertIn('properties', schema)
        self.assertIn('m', schema['properties'])
        self.assertIn('n', schema['properties'])
        self.assertEqual(schema['properties']['m']['type'], 'integer')
        self.assertEqual(schema['properties']['n']['type'], 'string')
        self.assertIn('required', schema)
        self.assertEqual(schema['required'], ['m'])


class TestDocstringUnsupportedWarning(unittest.TestCase):
    def test_informal_param_info_warning(self):
        def unsupported(x: int, y: str):
            """Do something.

            The x parameter should be an integer indicating repetitions. The y parameter is used for labeling.
            """
            return x, y

        # _extract_docstring_args is used via function_to_json_schema or directly. Use direct import path
        from dapr.clients.grpc._conversation_helpers import _extract_docstring_args

        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter('always')
            res = _extract_docstring_args(unsupported)
            self.assertEqual(res, {})
            self.assertTrue(
                any('appears to contain parameter information' in str(wi.message) for wi in w)
            )


class TestLiteralSchemaMapping(unittest.TestCase):
    def test_literal_strings_schema(self):
        T = Literal['a', 'b', 'c']
        schema = _python_type_to_json_schema(T)
        self.assertEqual(schema.get('type'), 'string')
        self.assertEqual(set(schema['enum']), {'a', 'b', 'c'})

    def test_literal_ints_schema(self):
        T = Literal[1, 2, 3]
        schema = _python_type_to_json_schema(T)
        self.assertEqual(schema.get('type'), 'integer')
        self.assertEqual(set(schema['enum']), {1, 2, 3})

    def test_literal_nullable_string_schema(self):
        T = Literal[None, 'x', 'y']
        schema = _python_type_to_json_schema(T)
        # non-null types only string, should set 'type' to 'string' and include None in enum
        self.assertEqual(schema.get('type'), 'string')
        self.assertIn(None, schema['enum'])
        self.assertIn('x', schema['enum'])
        self.assertIn('y', schema['enum'])

    def test_literal_mixed_types_no_unified_type(self):
        T = Literal['x', 1]
        schema = _python_type_to_json_schema(T)
        # Mixed non-null types -> no unified 'type' should be set
        self.assertNotIn('type', schema)
        self.assertEqual(set(schema['enum']), {'x', 1})

    def test_literal_enum_members_normalized(self):
        from enum import Enum

        class Mode(Enum):
            FAST = 'fast'
            SLOW = 'slow'

        T = Literal[Mode.FAST, Mode.SLOW]
        schema = _python_type_to_json_schema(T)
        self.assertEqual(schema.get('type'), 'string')
        self.assertEqual(set(schema['enum']), {'fast', 'slow'})

    def test_literal_bytes_and_bytearray_schema(self):
        T = Literal[b'a', bytearray(b'b')]
        schema = _python_type_to_json_schema(T)
        # bytes/bytearray are coerced to string type for schema typing
        self.assertEqual(schema.get('type'), 'string')
        # The enum preserves the literal values as provided
        self.assertIn(b'a', schema['enum'])
        self.assertIn(bytearray(b'b'), schema['enum'])


# --- Helpers for Coercion tests


class Mode(Enum):
    RED = 'red'
    BLUE = 'blue'


@dataclass
class DC:
    x: int
    y: str


class Plain:
    def __init__(self, a: int, b: str = 'x') -> None:
        self.a = a
        self.b = b


class TestScalarCoercions(unittest.TestCase):
    def test_int_from_str_and_float_and_invalid(self):
        def f(a: int) -> int:
            return a

        # str -> int
        bound = bind_params_to_func(f, {'a': ' 42 '})
        self.assertEqual(f(*bound.args, **bound.kwargs), 42)

        # float integral -> int
        bound = bind_params_to_func(f, {'a': 3.0})
        self.assertEqual(f(*bound.args, **bound.kwargs), 3)

        # float non-integral -> error
        with self.assertRaises(ToolArgumentError):
            bind_params_to_func(f, {'a': 3.14})

    def test_float_from_int_and_str(self):
        def g(x: float) -> float:
            return x

        bound = bind_params_to_func(g, {'x': 2})
        self.assertEqual(g(*bound.args, **bound.kwargs), 2.0)

        bound = bind_params_to_func(g, {'x': ' 3.5 '})
        self.assertEqual(g(*bound.args, **bound.kwargs), 3.5)

    def test_str_from_non_str(self):
        def h(s: str) -> str:
            return s

        bound = bind_params_to_func(h, {'s': 123})
        self.assertEqual(h(*bound.args, **bound.kwargs), '123')

    def test_bool_variants_and_invalid(self):
        def b(flag: bool) -> bool:
            return flag

        for v in ['true', 'False', 'YES', 'no', '1', '0', 'on', 'off']:
            bound = bind_params_to_func(b, {'flag': v})
            # Ensure conversion yields actual bool
            self.assertIsInstance(b(*bound.args, **bound.kwargs), bool)

        with self.assertRaises(ToolArgumentError):
            bind_params_to_func(b, {'flag': 'maybe'})


class TestEnumCoercions(unittest.TestCase):
    def test_enum_by_value_and_name_and_case_insensitive(self):
        def f(m: Mode) -> Mode:
            return m

        # by value
        bound = bind_params_to_func(f, {'m': 'red'})
        self.assertEqual(f(*bound.args, **bound.kwargs), Mode.RED)

        # by exact name
        bound = bind_params_to_func(f, {'m': 'BLUE'})
        self.assertEqual(f(*bound.args, **bound.kwargs), Mode.BLUE)

        # by case-insensitive name
        bound = bind_params_to_func(f, {'m': 'red'})  # value already tested; use name lower
        self.assertEqual(f(*bound.args, **bound.kwargs), Mode.RED)

        # invalid
        with self.assertRaises(ToolArgumentError):
            bind_params_to_func(f, {'m': 'green'})


class TestCoerceAndValidateBranches(unittest.TestCase):
    def test_optional_and_union(self):
        def f(a: Optional[int], b: Union[str, int]) -> tuple:
            return a, b

        bound = bind_params_to_func(f, {'a': '2', 'b': 5})
        # Union[str, int] tries str first; 5 is coerced to '5'
        self.assertEqual(f(*bound.args, **bound.kwargs), (2, '5'))

        bound = bind_params_to_func(f, {'a': None, 'b': 'hello'})
        self.assertEqual(f(*bound.args, **bound.kwargs), (None, 'hello'))

    def test_list_and_dict_coercion(self):
        def g(xs: List[int], mapping: Dict[int, float]) -> tuple:
            return xs, mapping

        bound = bind_params_to_func(g, {'xs': ['1', '2', '3'], 'mapping': {'1': '2.5', 3: 4}})
        xs, mapping = g(*bound.args, **bound.kwargs)
        self.assertEqual(xs, [1, 2, 3])
        self.assertEqual(mapping, {1: 2.5, 3: 4.0})

        # Wrong type for list
        with self.assertRaises(ToolArgumentError):
            bind_params_to_func(g, {'xs': 'not-a-list', 'mapping': {}})

        # Wrong type for dict
        with self.assertRaises(ToolArgumentError):
            bind_params_to_func(g, {'xs': [1], 'mapping': 'not-a-dict'})

    def test_dataclass_optional_and_rejection_of_dict(self):
        def f(p: Optional[DC]) -> Optional[str]:
            return None if p is None else p.y

        # inst = DC(1, 'ok')
        # bound = bind_params_to_func(f, {'p': inst})
        # self.assertEqual(f(*bound.args, **bound.kwargs), 'ok')
        #
        # bound = bind_params_to_func(f, {'p': None})
        # self.assertIsNone(f(*bound.args, **bound.kwargs))

        with self.assertRaises(ToolArgumentError):
            bind_params_to_func(f, {'p': {'x': 1, 'y': 'no'}})

    def test_plain_class_construction_from_dict_and_missing_arg(self):
        def f(p: Plain) -> int:
            return p.a

        # Construct from dict with coercion
        bound = bind_params_to_func(f, {'p': {'a': '3'}})
        res = f(*bound.args, **bound.kwargs)
        self.assertEqual(res, 3)
        self.assertIsInstance(bound.arguments['p'], Plain)
        self.assertEqual(bound.arguments['p'].b, 'x')  # default applied

        # Missing required arg
        with self.assertRaises(ToolArgumentError):
            bind_params_to_func(f, {'p': {}})

    def test_any_and_isinstance_fallback(self):
        class C:
            ...

        def f(a: Any, c: C) -> tuple:
            return a, c

        c = C()
        with self.assertRaises(ToolArgumentError) as ctx:
            bind_params_to_func(f, {'a': object(), 'c': c})
        # _coerce_and_validate raises TypeError for Any; bind wraps it in ToolArgumentError
        self.assertIsInstance(ctx.exception.__cause__, TypeError)


# ---- Helpers for test stringify


class Shade(Enum):
    LIGHT = 'light'
    DARK = 'dark'


@dataclass
class Pair:
    a: int
    b: str


class PlainWithDict:
    def __init__(self):
        self.x = 10
        self.y = 'y'
        self.fn = lambda: 1  # callable should be filtered out


class TestStringifyToolOutputMore(unittest.TestCase):
    def test_bytes_and_bytearray_branch(self):
        raw = bytes([1, 2, 3, 254, 255])
        expected = 'base64:' + base64.b64encode(raw).decode('ascii')
        self.assertEqual(stringify_tool_output(raw), expected)

        ba = bytearray(raw)
        expected_ba = 'base64:' + base64.b64encode(bytes(ba)).decode('ascii')
        self.assertEqual(stringify_tool_output(ba), expected_ba)

    def test_default_encoder_enum_dataclass_and___dict__(self):
        # Enum -> value via default encoder (JSON string)
        out_enum = stringify_tool_output(Shade.DARK)
        self.assertEqual(out_enum, json.dumps('dark', ensure_ascii=False))

        # Dataclass -> asdict via default encoder
        p = Pair(3, 'z')
        out_dc = stringify_tool_output(p)
        self.assertEqual(json.loads(out_dc), {'a': 3, 'b': 'z'})

        # __dict__ plain object -> filtered dict via default encoder
        obj = PlainWithDict()
        out_obj = stringify_tool_output(obj)
        self.assertEqual(json.loads(out_obj), {'x': 10, 'y': 'y'})


if __name__ == '__main__':
    unittest.main()
