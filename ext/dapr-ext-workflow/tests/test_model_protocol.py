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
from types import SimpleNamespace
from typing import Optional

from dapr.ext.workflow import _model_protocol
from pydantic import BaseModel, ValidationError


class Order(BaseModel):
    order_id: str
    amount: float


class ModelProtocolTest(unittest.TestCase):
    """Model-protocol helpers exercised against real Pydantic models."""

    def test_is_model_recognizes_pydantic_instance(self):
        self.assertTrue(_model_protocol.is_model(Order(order_id='o1', amount=1.0)))

    def test_is_model_class_recognizes_pydantic_class(self):
        self.assertTrue(_model_protocol.is_model_class(Order))

    def test_is_model_rejects_plain_objects(self):
        self.assertFalse(_model_protocol.is_model(None))
        self.assertFalse(_model_protocol.is_model({'a': 1}))
        self.assertFalse(_model_protocol.is_model(object()))
        self.assertFalse(_model_protocol.is_model_class(dict))
        self.assertFalse(_model_protocol.is_model_class(None))

    def test_dump_model_uses_json_mode(self):
        dumped = _model_protocol.dump_model(Order(order_id='o1', amount=2.5))
        self.assertEqual(dumped, {'order_id': 'o1', 'amount': 2.5})

    def test_dump_model_rejects_non_model(self):
        with self.assertRaises(TypeError):
            _model_protocol.dump_model({'order_id': 'o1', 'amount': 1.0})

    def test_coerce_to_model_from_dict(self):
        order = _model_protocol.coerce_to_model({'order_id': 'o1', 'amount': 3.0}, Order)
        self.assertIsInstance(order, Order)
        self.assertEqual(order.order_id, 'o1')
        self.assertEqual(order.amount, 3.0)

    def test_coerce_to_model_from_simplenamespace(self):
        ns = SimpleNamespace(order_id='o2', amount=4.0)
        order = _model_protocol.coerce_to_model(ns, Order)
        self.assertIsInstance(order, Order)
        self.assertEqual(order.order_id, 'o2')
        self.assertEqual(order.amount, 4.0)

    def test_coerce_to_model_passthrough_when_already_instance(self):
        original = Order(order_id='o3', amount=5.0)
        self.assertIs(_model_protocol.coerce_to_model(original, Order), original)

    def test_coerce_to_model_rejects_unsupported_shape(self):
        with self.assertRaises(TypeError):
            _model_protocol.coerce_to_model(42, Order)
        with self.assertRaises(TypeError):
            _model_protocol.coerce_to_model([1, 2, 3], Order)

    def test_coerce_to_model_rejects_non_model_class(self):
        with self.assertRaises(TypeError):
            _model_protocol.coerce_to_model({'x': 1}, dict)

    def test_coerce_to_model_raises_validation_error_on_invalid_payload(self):
        with self.assertRaises(ValidationError):
            _model_protocol.coerce_to_model({'order_id': 'o1'}, Order)  # missing amount


class ResolveInputTest(unittest.TestCase):
    def test_resolves_pydantic_annotation(self):
        def my_activity(ctx, order: Order):
            return order

        self.assertEqual(_model_protocol.resolve_input(my_activity), (True, Order))

    def test_unwraps_optional(self):
        def my_activity(ctx, order: Optional[Order] = None):
            return order

        self.assertEqual(_model_protocol.resolve_input(my_activity), (True, Order))

    def test_accepts_input_without_annotation(self):
        def my_activity(ctx, order):
            return order

        self.assertEqual(_model_protocol.resolve_input(my_activity), (True, None))

    def test_accepts_input_with_non_model_annotation(self):
        def my_activity(ctx, order: dict):
            return order

        self.assertEqual(_model_protocol.resolve_input(my_activity), (True, None))

    def test_ctx_only_does_not_accept_input(self):
        def my_activity(ctx):
            return None

        self.assertEqual(_model_protocol.resolve_input(my_activity), (False, None))


class _DuckModelNoModeKwarg:
    """Non-Pydantic class matching the model protocol without a mode kwarg.

    Exercises the _supports_mode_kwarg fallback path — real Pydantic v2 always
    accepts `mode`, so this behavior needs a non-Pydantic class to hit.
    """

    def __init__(self, name: str, value: int):
        self.name = name
        self.value = value

    def model_dump(self) -> dict:
        return {'name': self.name, 'value': self.value}

    @classmethod
    def model_validate(cls, data: dict) -> '_DuckModelNoModeKwarg':
        return cls(name=data['name'], value=data['value'])


class ProtocolOpennessTest(unittest.TestCase):
    """The protocol is open to any class implementing model_dump/model_validate."""

    def test_dump_falls_back_when_model_dump_has_no_mode_kwarg(self):
        dumped = _model_protocol.dump_model(_DuckModelNoModeKwarg('x', 7))
        self.assertEqual(dumped, {'name': 'x', 'value': 7})

    def test_is_model_class_rejects_partial_implementations(self):
        class DumpOnly:
            def model_dump(self):
                return {}

        class ValidateOnly:
            @classmethod
            def model_validate(cls, data):
                return cls()

        self.assertFalse(_model_protocol.is_model_class(DumpOnly))
        self.assertFalse(_model_protocol.is_model_class(ValidateOnly))
