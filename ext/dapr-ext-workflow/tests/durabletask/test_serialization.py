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

from collections import namedtuple
from dataclasses import dataclass
from types import SimpleNamespace

from dapr.ext.workflow._durabletask.internal.shared import AUTO_SERIALIZED, from_json, to_json
from pydantic import BaseModel


@dataclass
class SamplePayload:
    count: int
    name: str


def test_to_json_roundtrip_dataclass():
    payload = SamplePayload(count=5, name='widgets')
    encoded = to_json(payload)

    assert AUTO_SERIALIZED in encoded

    decoded = from_json(encoded)
    assert isinstance(decoded, SimpleNamespace)
    assert decoded.count == 5
    assert decoded.name == 'widgets'


def test_to_json_roundtrip_simplenamespace():
    payload = SimpleNamespace(foo='bar', baz=42)
    encoded = to_json(payload)

    assert AUTO_SERIALIZED in encoded

    decoded = from_json(encoded)
    assert isinstance(decoded, SimpleNamespace)
    assert decoded.foo == 'bar'
    assert decoded.baz == 42


def test_to_json_plain_dict_passthrough():
    payload = {'foo': 'bar', 'baz': 1}
    encoded = to_json(payload)

    assert AUTO_SERIALIZED not in encoded

    decoded = from_json(encoded)
    assert isinstance(decoded, dict)
    assert decoded == {'foo': 'bar', 'baz': 1}


def test_to_json_namedtuple_roundtrip():
    Point = namedtuple('Point', ['x', 'y'])
    payload = Point(3, 4)
    encoded = to_json(payload)

    assert AUTO_SERIALIZED in encoded

    decoded = from_json(encoded)
    assert isinstance(decoded, SimpleNamespace)
    assert decoded.x == 3
    assert decoded.y == 4


def test_to_json_nested_dataclass_collection():
    payload = [
        SamplePayload(count=1, name='first'),
        SamplePayload(count=2, name='second'),
    ]
    encoded = to_json(payload)

    assert encoded.count(AUTO_SERIALIZED) >= 2

    decoded = from_json(encoded)
    assert isinstance(decoded, list)
    assert [item.count for item in decoded] == [1, 2]
    assert [item.name for item in decoded] == ['first', 'second']


class Order(BaseModel):
    order_id: str
    amount: float


class Item(BaseModel):
    sku: str
    qty: int


def test_to_json_pydantic_model_emits_plain_dict():
    encoded = to_json(Order(order_id='o1', amount=9.99))

    # Pydantic payloads must not carry the AUTO_SERIALIZED marker so that
    # cross-language and marker-unaware receivers can read them as plain JSON.
    assert AUTO_SERIALIZED not in encoded

    decoded = from_json(encoded)
    assert decoded == {'order_id': 'o1', 'amount': 9.99}


def test_to_json_pydantic_model_in_list_emits_plain_dicts():
    encoded = to_json([Item(sku='A', qty=1), Item(sku='B', qty=2)])

    assert AUTO_SERIALIZED not in encoded

    decoded = from_json(encoded)
    assert decoded == [{'sku': 'A', 'qty': 1}, {'sku': 'B', 'qty': 2}]


def test_to_json_pydantic_and_dataclass_coexist():
    payload = {
        'order': Order(order_id='o1', amount=1.0),
        'detail': SamplePayload(count=3, name='x'),
    }
    encoded = to_json(payload)

    # Dataclass still carries AUTO_SERIALIZED; Pydantic does not.
    assert encoded.count(AUTO_SERIALIZED) == 1

    decoded = from_json(encoded)
    assert decoded['order'] == {'order_id': 'o1', 'amount': 1.0}
    assert isinstance(decoded['detail'], SimpleNamespace)
    assert decoded['detail'].count == 3
