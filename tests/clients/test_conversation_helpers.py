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

import json
import base64
from dataclasses import dataclass
from enum import Enum

from typing import Dict, List, Literal, Optional, Union, Set


from dapr.clients.grpc._conversation_helpers import (
    stringify_tool_output,
    bind_params_to_func,
    function_to_json_schema,
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
