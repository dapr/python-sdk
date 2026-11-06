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
from dataclasses import dataclass
from types import SimpleNamespace
from typing import Optional

from dapr.ext.rag._wire import from_wire, to_wire


@dataclass(frozen=True, slots=True)
class _FlatExample:
    name: str
    count: int = 0
    note: Optional[str] = None


class ToWireTest(unittest.TestCase):
    def test_converts_a_dataclass_instance_to_a_plain_dict(self):
        value = _FlatExample(name='a', count=2)
        self.assertEqual(to_wire(value), {'name': 'a', 'count': 2, 'note': None})

    def test_passes_non_dataclass_values_through_unchanged(self):
        self.assertEqual(to_wire({'already': 'a dict'}), {'already': 'a dict'})
        self.assertEqual(to_wire('a string'), 'a string')
        self.assertIsNone(to_wire(None))

    def test_does_not_treat_a_dataclass_type_itself_as_an_instance(self):
        # dataclasses.is_dataclass(_FlatExample) is True for the *class* too;
        # to_wire must only convert instances.
        self.assertIs(to_wire(_FlatExample), _FlatExample)


class FromWireTest(unittest.TestCase):
    def test_reconstructs_from_a_dict(self):
        raw = {'name': 'a', 'count': 2, 'note': None}
        result = from_wire(raw, _FlatExample)
        self.assertEqual(result, _FlatExample(name='a', count=2))

    def test_reconstructs_from_a_simple_namespace(self):
        raw = SimpleNamespace(name='a', count=2, note='hi')
        result = from_wire(raw, _FlatExample)
        self.assertEqual(result, _FlatExample(name='a', count=2, note='hi'))

    def test_passes_through_an_existing_instance(self):
        value = _FlatExample(name='a')
        self.assertIs(from_wire(value, _FlatExample), value)

    def test_raises_type_error_for_an_unsupported_shape(self):
        with self.assertRaises(TypeError):
            from_wire(42, _FlatExample)

    def test_round_trips_through_to_wire(self):
        original = _FlatExample(name='round-trip', count=7, note='ok')
        self.assertEqual(from_wire(to_wire(original), _FlatExample), original)


if __name__ == '__main__':
    unittest.main()
