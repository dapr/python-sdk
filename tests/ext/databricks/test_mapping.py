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

import json
import unittest
from datetime import date, datetime, timezone
from decimal import Decimal

from dapr.ext.databricks.mapping import default_row_mapper
from tests.ext.databricks._fakes import FakeRow


class DefaultRowMapperTests(unittest.TestCase):
    def test_simple_fields_pass_through(self):
        row = FakeRow(order_id=123, customer_id=456, status='READY')
        self.assertEqual(
            default_row_mapper(row),
            {'order_id': 123, 'customer_id': 456, 'status': 'READY'},
        )

    def test_result_is_json_serializable(self):
        row = FakeRow(order_id=123, status='READY')
        json.dumps(default_row_mapper(row))  # must not raise

    def test_datetime_becomes_isoformat_string(self):
        when = datetime(2026, 1, 2, 3, 4, 5, tzinfo=timezone.utc)
        row = FakeRow(created_at=when)
        self.assertEqual(default_row_mapper(row)['created_at'], when.isoformat())

    def test_date_becomes_isoformat_string(self):
        day = date(2026, 1, 2)
        row = FakeRow(order_date=day)
        self.assertEqual(default_row_mapper(row)['order_date'], day.isoformat())

    def test_decimal_becomes_string_to_avoid_precision_loss(self):
        row = FakeRow(amount=Decimal('19.999999999999999999'))
        mapped = default_row_mapper(row)
        self.assertEqual(mapped['amount'], '19.999999999999999999')
        self.assertIsInstance(mapped['amount'], str)

    def test_bytes_become_base64_string(self):
        row = FakeRow(payload=b'\x00\x01\xff')
        mapped = default_row_mapper(row)
        self.assertEqual(mapped['payload'], 'AAH/')

    def test_nested_row_is_recursively_converted(self):
        row = FakeRow(order_id=1, customer=FakeRow(id=9, name='Ada'))
        mapped = default_row_mapper(row)
        self.assertEqual(mapped['customer'], {'id': 9, 'name': 'Ada'})

    def test_list_of_rows_is_recursively_converted(self):
        row = FakeRow(items=[FakeRow(sku='A'), FakeRow(sku='B')])
        mapped = default_row_mapper(row)
        self.assertEqual(mapped['items'], [{'sku': 'A'}, {'sku': 'B'}])


class CustomInputMapperTests(unittest.TestCase):
    def test_custom_mapper_overrides_default_shape(self):
        row = FakeRow(customer_id=456, status='READY', internal_score=0.87)

        def custom_mapper(r):
            return {'customer': r['customer_id'], 'status': r['status']}

        mapped = custom_mapper(row)
        self.assertEqual(mapped, {'customer': 456, 'status': 'READY'})
        self.assertNotIn('internal_score', mapped)


if __name__ == '__main__':
    unittest.main()
