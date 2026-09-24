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

Tests for register_workflow_sink's pyspark.pipelines wiring. pyspark is
never installed for these tests (see AGENTS.md): a fake module is injected
into sys.modules for the "inside Lakeflow" tests, and removed/absent for the
"outside Lakeflow" test, matching how the extension is actually used.
"""

import sys
import types
import unittest
from unittest import mock

from dapr.ext.databricks.batch_handler import DaprWorkflowBatchHandler
from tests.ext.databricks._fakes import FakeDataFrame, FakeRow, FakeWorkflowClient


class FakePipelinesModule(types.ModuleType):
    """Fakes just enough of ``pyspark.pipelines`` for ``register_workflow_sink``."""

    def __init__(self):
        super().__init__('pyspark.pipelines')
        self.registered_sinks = {}

    def foreach_batch_sink(self, name=None, **_kwargs):
        def decorator(fn):
            self.registered_sinks[name or fn.__name__] = fn
            return fn

        return decorator


def _install_fake_pyspark():
    fake_pipelines = FakePipelinesModule()
    fake_pyspark = types.ModuleType('pyspark')
    fake_pyspark.pipelines = fake_pipelines
    return fake_pyspark, fake_pipelines


class RegisterWorkflowSinkOutsideLakeflowTests(unittest.TestCase):
    def test_clear_error_when_pyspark_is_unavailable(self):
        # No pyspark.* entries are patched into sys.modules here, and the
        # module is not actually installed in this environment (by design:
        # see the `databricks` extra in pyproject.toml).
        with mock.patch.dict(sys.modules):
            sys.modules.pop('pyspark', None)
            sys.modules.pop('pyspark.pipelines', None)

            from dapr.ext.databricks.sink import register_workflow_sink

            with self.assertRaises(ImportError) as ctx:
                register_workflow_sink(name='orders', workflow='process_order')

        self.assertIn('pyspark.pipelines.foreach_batch_sink', str(ctx.exception))
        self.assertIn('Databricks Lakeflow', str(ctx.exception))


class RegisterWorkflowSinkInsideLakeflowTests(unittest.TestCase):
    def setUp(self):
        self.fake_pyspark, self.fake_pipelines = _install_fake_pyspark()
        patcher = mock.patch.dict(
            sys.modules,
            {'pyspark': self.fake_pyspark, 'pyspark.pipelines': self.fake_pipelines},
        )
        patcher.start()
        self.addCleanup(patcher.stop)

        client_patcher = mock.patch(
            'dapr.ext.databricks.batch_handler.DaprWorkflowClient', autospec=False
        )
        self.mock_client_cls = client_patcher.start()
        self.addCleanup(client_patcher.stop)
        self.fake_client = FakeWorkflowClient()
        self.mock_client_cls.return_value = self.fake_client

    def test_registers_a_foreach_batch_sink_under_the_given_name(self):
        from dapr.ext.databricks.sink import register_workflow_sink

        handler = register_workflow_sink(
            name='order_actions', workflow='process_order', id_field='order_id'
        )

        self.assertIn('order_actions', self.fake_pipelines.registered_sinks)
        self.assertIsInstance(handler, DaprWorkflowBatchHandler)

    def test_registered_sink_delegates_to_the_handler(self):
        from dapr.ext.databricks.sink import register_workflow_sink

        register_workflow_sink(
            name='order_actions', workflow='process_order', id_field='order_id', namespace='orders'
        )
        sink_fn = self.fake_pipelines.registered_sinks['order_actions']

        sink_fn(FakeDataFrame([FakeRow(order_id=123)]), 1)

        self.assertEqual(len(self.fake_client.scheduled), 1)
        _, instance_id, _ = self.fake_client.scheduled[0]
        self.assertEqual(instance_id, 'orders-order_actions-v1-123')

    def test_invalid_configuration_raises_before_registering_pyspark_sink(self):
        from dapr.ext.databricks.exceptions import SinkConfigurationError
        from dapr.ext.databricks.sink import register_workflow_sink

        with self.assertRaises(SinkConfigurationError):
            register_workflow_sink(
                name='order_actions',
                workflow='process_order',
                id_field='order_id',
                id_fields=['a', 'b'],
            )

        self.assertNotIn('order_actions', self.fake_pipelines.registered_sinks)


if __name__ == '__main__':
    unittest.main()
