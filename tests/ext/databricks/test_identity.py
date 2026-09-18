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

from dapr.ext.databricks.exceptions import MissingBusinessKeyError
from dapr.ext.databricks.identity import (
    _MAX_INSTANCE_ID_LENGTH,
    derive_instance_id,
    extract_business_key,
    sanitize_segment,
)
from tests.ext.databricks._fakes import FakeRow

_ALLOWED_CHARS = set('abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-')


class SanitizeSegmentTests(unittest.TestCase):
    def test_clean_short_segment_is_unchanged(self):
        self.assertEqual(sanitize_segment('order-123_abc'), 'order-123_abc')

    def test_invalid_characters_are_hashed_deterministically(self):
        first = sanitize_segment('order/123:456')
        second = sanitize_segment('order/123:456')

        self.assertEqual(first, second)
        self.assertTrue(set(first) <= _ALLOWED_CHARS)
        self.assertNotEqual(first, 'order/123:456')

    def test_different_dirty_inputs_hash_differently(self):
        self.assertNotEqual(sanitize_segment('a/b'), sanitize_segment('a/c'))

    def test_unicode_input_is_hashed_and_stable(self):
        first = sanitize_segment('café-北京-🎉')
        second = sanitize_segment('café-北京-🎉')

        self.assertEqual(first, second)
        self.assertTrue(set(first) <= _ALLOWED_CHARS)

    def test_distinct_unicode_inputs_do_not_collide(self):
        # A naive ASCII-fold/transliterate approach could collapse distinct
        # non-Latin business keys onto the same (near-empty) output; hashing
        # the whole segment instead must keep them distinct.
        self.assertNotEqual(sanitize_segment('北京'), sanitize_segment('上海'))

    def test_empty_string_is_hashed_not_dropped(self):
        result = sanitize_segment('')
        self.assertTrue(result)
        self.assertTrue(set(result) <= _ALLOWED_CHARS)

    def test_overlong_clean_segment_is_hashed(self):
        long_clean = 'a' * 500
        result = sanitize_segment(long_clean)
        self.assertNotEqual(result, long_clean)
        self.assertLessEqual(len(result), 64)


class ExtractBusinessKeyTests(unittest.TestCase):
    def test_single_id_field(self):
        row = FakeRow(order_id=123, status='READY')
        key = extract_business_key(
            row, batch_id=1, id_field='order_id', id_fields=None, instance_id_factory=None
        )
        self.assertEqual(key, '123')

    def test_composite_id_fields_join_in_order(self):
        row = FakeRow(account_id='A1', transaction_id='T9')
        key = extract_business_key(
            row,
            batch_id=1,
            id_field=None,
            id_fields=['account_id', 'transaction_id'],
            instance_id_factory=None,
        )
        self.assertEqual(key, 'A1_T9')

    def test_instance_id_factory_takes_priority_and_receives_batch_id(self):
        seen_args = []

        def factory(row, batch_id):
            seen_args.append((row['order_id'], batch_id))
            return f'custom-{row["order_id"]}'

        row = FakeRow(order_id=42)
        key = extract_business_key(
            row,
            batch_id=7,
            id_field='order_id',  # would be ignored: factory takes priority
            id_fields=None,
            instance_id_factory=factory,
        )
        self.assertEqual(key, 'custom-42')
        self.assertEqual(seen_args, [(42, 7)])

    def test_no_strategy_configured_returns_none(self):
        row = FakeRow(order_id=42)
        key = extract_business_key(
            row, batch_id=1, id_field=None, id_fields=None, instance_id_factory=None
        )
        self.assertIsNone(key)

    def test_missing_id_field_raises(self):
        row = FakeRow(customer_id=1)
        with self.assertRaises(MissingBusinessKeyError):
            extract_business_key(
                row, batch_id=1, id_field='order_id', id_fields=None, instance_id_factory=None
            )

    def test_null_id_field_raises(self):
        row = FakeRow(order_id=None)
        with self.assertRaises(MissingBusinessKeyError):
            extract_business_key(
                row, batch_id=1, id_field='order_id', id_fields=None, instance_id_factory=None
            )

    def test_missing_field_within_composite_key_raises(self):
        row = FakeRow(account_id='A1')
        with self.assertRaises(MissingBusinessKeyError):
            extract_business_key(
                row,
                batch_id=1,
                id_field=None,
                id_fields=['account_id', 'transaction_id'],
                instance_id_factory=None,
            )


class DeriveInstanceIdTests(unittest.TestCase):
    def test_deterministic_for_same_business_key(self):
        first = derive_instance_id(
            namespace='orders',
            sink_name='order_actions',
            generation='v1',
            business_key='123',
            batch_id=42,
            record_index=0,
        )
        second = derive_instance_id(
            namespace='orders',
            sink_name='order_actions',
            generation='v1',
            business_key='123',
            batch_id=999,  # different batch/record: must not matter when a business key exists
            record_index=5,
        )
        self.assertEqual(first, second)
        self.assertEqual(first, 'orders-order_actions-v1-123')

    def test_different_business_keys_produce_different_ids(self):
        def make_id(key):
            return derive_instance_id(
                namespace='orders',
                sink_name='order_actions',
                generation='v1',
                business_key=key,
                batch_id=1,
                record_index=0,
            )

        self.assertNotEqual(make_id('123'), make_id('124'))

    def test_generation_changes_identity(self):
        def make_id(generation):
            return derive_instance_id(
                namespace='orders',
                sink_name='order_actions',
                generation=generation,
                business_key='123',
                batch_id=1,
                record_index=0,
            )

        self.assertNotEqual(make_id('v1'), make_id('v2'))

    def test_namespace_changes_identity(self):
        def make_id(namespace):
            return derive_instance_id(
                namespace=namespace,
                sink_name='order_actions',
                generation='v1',
                business_key='123',
                batch_id=1,
                record_index=0,
            )

        self.assertNotEqual(make_id('orders'), make_id('fraud'))

    def test_fallback_identity_uses_batch_and_record_index_when_no_business_key(self):
        instance_id = derive_instance_id(
            namespace='orders',
            sink_name='order_actions',
            generation='v1',
            business_key=None,
            batch_id=42,
            record_index=3,
        )
        self.assertEqual(instance_id, 'orders-order_actions-v1-42-3')

    def test_fallback_identity_differs_by_record_index(self):
        def make_id(idx):
            return derive_instance_id(
                namespace='orders',
                sink_name='order_actions',
                generation='v1',
                business_key=None,
                batch_id=42,
                record_index=idx,
            )

        self.assertNotEqual(make_id(0), make_id(1))

    def test_result_always_within_length_bound(self):
        instance_id = derive_instance_id(
            namespace='n' * 100,
            sink_name='s' * 100,
            generation='g' * 100,
            business_key='k' * 500,
            batch_id=1,
            record_index=0,
        )
        self.assertLessEqual(len(instance_id), _MAX_INSTANCE_ID_LENGTH)

    def test_pathologically_long_clean_prefix_still_distinguishes_records(self):
        # namespace/sink/generation alone can exceed the instance-id budget
        # even though each segment is individually "clean". The final digest
        # must never be truncated away, or every record in the sink would
        # collide onto the same instance ID.
        def make_id(key):
            return derive_instance_id(
                namespace='n' * 80,
                sink_name='s' * 80,
                generation='g' * 80,
                business_key=key,
                batch_id=1,
                record_index=0,
            )

        first, second = make_id('key-one'), make_id('key-two')
        self.assertLessEqual(len(first), _MAX_INSTANCE_ID_LENGTH)
        self.assertNotEqual(first, second)

    def test_only_valid_instance_id_characters_are_produced(self):
        instance_id = derive_instance_id(
            namespace='orders',
            sink_name='order_actions',
            generation='v1',
            business_key='id with spaces/slashes:colons',
            batch_id=1,
            record_index=0,
        )
        self.assertTrue(set(instance_id) <= _ALLOWED_CHARS)


if __name__ == '__main__':
    unittest.main()
