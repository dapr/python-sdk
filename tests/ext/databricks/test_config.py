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

from dapr.ext.databricks.config import WorkflowSinkConfig
from dapr.ext.databricks.exceptions import SinkConfigurationError
from dapr.ext.databricks.mapping import default_row_mapper


class WorkflowSinkConfigTests(unittest.TestCase):
    def test_minimal_valid_config(self):
        config = WorkflowSinkConfig(name='orders', workflow='process_order', id_field='order_id')
        self.assertEqual(config.namespace, 'default')
        self.assertEqual(config.generation, 'v1')
        self.assertTrue(config.metadata)
        self.assertEqual(config.max_in_flight, 8)
        self.assertIsNone(config.max_records_per_batch)

    def test_empty_name_rejected(self):
        with self.assertRaises(SinkConfigurationError):
            WorkflowSinkConfig(name='', workflow='process_order')

    def test_empty_workflow_rejected(self):
        with self.assertRaises(SinkConfigurationError):
            WorkflowSinkConfig(name='orders', workflow='')

    def test_empty_namespace_rejected(self):
        with self.assertRaises(SinkConfigurationError):
            WorkflowSinkConfig(name='orders', workflow='process_order', namespace='')

    def test_empty_generation_rejected(self):
        with self.assertRaises(SinkConfigurationError):
            WorkflowSinkConfig(name='orders', workflow='process_order', generation='')

    def test_id_field_and_id_fields_together_rejected(self):
        with self.assertRaises(SinkConfigurationError):
            WorkflowSinkConfig(
                name='orders',
                workflow='process_order',
                id_field='order_id',
                id_fields=['account_id', 'transaction_id'],
            )

    def test_id_field_and_instance_id_factory_together_rejected(self):
        with self.assertRaises(SinkConfigurationError):
            WorkflowSinkConfig(
                name='orders',
                workflow='process_order',
                id_field='order_id',
                instance_id_factory=lambda row, batch_id: 'x',
            )

    def test_empty_id_fields_rejected(self):
        with self.assertRaises(SinkConfigurationError):
            WorkflowSinkConfig(name='orders', workflow='process_order', id_fields=[])

    def test_max_in_flight_must_be_positive(self):
        with self.assertRaises(SinkConfigurationError):
            WorkflowSinkConfig(name='orders', workflow='process_order', max_in_flight=0)

    def test_max_records_per_batch_must_be_positive_when_set(self):
        with self.assertRaises(SinkConfigurationError):
            WorkflowSinkConfig(name='orders', workflow='process_order', max_records_per_batch=0)

    def test_row_mapper_defaults_to_default_row_mapper(self):
        config = WorkflowSinkConfig(name='orders', workflow='process_order')
        self.assertIs(config.row_mapper, default_row_mapper)

    def test_row_mapper_uses_configured_input_mapper(self):
        def custom_mapper(row):
            return {'x': 1}

        config = WorkflowSinkConfig(
            name='orders', workflow='process_order', input_mapper=custom_mapper
        )
        self.assertIs(config.row_mapper, custom_mapper)

    def test_config_is_immutable(self):
        config = WorkflowSinkConfig(name='orders', workflow='process_order')
        with self.assertRaises(Exception):
            config.name = 'other'  # type: ignore[misc]


if __name__ == '__main__':
    unittest.main()
