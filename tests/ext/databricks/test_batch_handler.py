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

import threading
import time
import unittest

import grpc

from dapr.ext.databricks.batch_handler import DaprWorkflowBatchHandler
from dapr.ext.databricks.config import WorkflowSinkConfig
from dapr.ext.databricks.exceptions import DaprDatabricksSinkError
from tests.ext.databricks._fakes import (
    FakeDataFrame,
    FakeRow,
    FakeWorkflowClient,
    SimulatedRpcError,
)


def _order_row(order_id, customer_id=1, status='READY'):
    return FakeRow(order_id=order_id, customer_id=customer_id, status=status)


class BasicSchedulingTests(unittest.TestCase):
    def test_one_row_schedules_one_workflow(self):
        client = FakeWorkflowClient()
        config = WorkflowSinkConfig(
            name='order_actions', workflow='process_order', id_field='order_id', namespace='orders'
        )
        handler = DaprWorkflowBatchHandler(config, workflow_client=client)

        handler.process(FakeDataFrame([_order_row(123)]), batch_id=1)

        self.assertEqual(len(client.scheduled), 1)
        workflow, instance_id, payload = client.scheduled[0]
        self.assertEqual(workflow, 'process_order')
        self.assertEqual(instance_id, 'orders-order_actions-v1-123')
        self.assertEqual(payload['data'], {'order_id': 123, 'customer_id': 1, 'status': 'READY'})

    def test_reprocessing_same_row_does_not_duplicate(self):
        client = FakeWorkflowClient()
        config = WorkflowSinkConfig(
            name='order_actions', workflow='process_order', id_field='order_id', namespace='orders'
        )
        handler = DaprWorkflowBatchHandler(config, workflow_client=client)

        handler.process(FakeDataFrame([_order_row(123)]), batch_id=1)
        handler.process(FakeDataFrame([_order_row(123)]), batch_id=1)

        self.assertEqual(len(client.scheduled), 1)  # only ever scheduled once
        self.assertEqual(client.schedule_calls.count('orders-order_actions-v1-123'), 1)


class MicroBatchRetryTests(unittest.TestCase):
    """The most important scenario: batch 42 has records A and B, B fails on
    the first attempt, and the batch retry must produce exactly one workflow
    for A and one for B — no duplicate for A, no missing execution for B."""

    def test_partial_failure_then_retry_yields_exactly_one_workflow_each(self):
        client = FakeWorkflowClient()
        config = WorkflowSinkConfig(
            name='order_actions',
            workflow='process_order',
            id_field='order_id',
            namespace='orders',
            max_in_flight=1,  # deterministic ordering for this test
        )
        handler = DaprWorkflowBatchHandler(config, workflow_client=client)
        batch = FakeDataFrame([_order_row('A'), _order_row('B')])

        a_instance_id = 'orders-order_actions-v1-A'
        b_instance_id = 'orders-order_actions-v1-B'
        client.raise_on_schedule[b_instance_id] = SimulatedRpcError(
            grpc.StatusCode.UNAVAILABLE, 'dapr sidecar unavailable'
        )

        with self.assertRaises(DaprDatabricksSinkError):
            handler.process(batch, batch_id=42)

        self.assertIn(a_instance_id, client.existing)
        self.assertNotIn(b_instance_id, client.existing)
        self.assertEqual(len(client.scheduled), 1)

        # Lakeflow retries the same micro-batch (same rows, same batch_id).
        handler.process(FakeDataFrame([_order_row('A'), _order_row('B')]), batch_id=42)

        # A is found already-existing on retry, so it is never re-attempted.
        # B genuinely failed the first attempt, so it is legitimately
        # attempted twice — the invariant is that it *succeeds* exactly once.
        self.assertEqual(client.schedule_calls.count(a_instance_id), 1)
        self.assertEqual(client.schedule_calls.count(b_instance_id), 2)
        scheduled_ids = [instance_id for _, instance_id, _ in client.scheduled]
        self.assertEqual(sorted(scheduled_ids), sorted([a_instance_id, b_instance_id]))
        self.assertEqual(len(client.scheduled), 2)  # exactly one workflow for A, one for B

    def test_lost_response_is_recovered_on_retry_without_duplicate(self):
        client = FakeWorkflowClient()
        config = WorkflowSinkConfig(
            name='order_actions', workflow='process_order', id_field='order_id', namespace='orders'
        )
        handler = DaprWorkflowBatchHandler(config, workflow_client=client)
        instance_id = 'orders-order_actions-v1-123'

        # Dapr accepts the schedule call durably, but the client never
        # observes success (e.g. the response is lost to a network blip).
        client.raise_on_schedule[instance_id] = SimulatedRpcError(
            grpc.StatusCode.DEADLINE_EXCEEDED, 'deadline exceeded'
        )
        client.lost_response_for.add(instance_id)

        with self.assertRaises(DaprDatabricksSinkError):
            handler.process(FakeDataFrame([_order_row(123)]), batch_id=1)

        handler.process(FakeDataFrame([_order_row(123)]), batch_id=1)  # Lakeflow retries

        self.assertEqual(client.schedule_calls, [instance_id])  # exactly one schedule attempt ever
        self.assertEqual(len(client.scheduled), 0)  # that one attempt never observed success
        self.assertEqual(client.get_state_calls.count(instance_id), 2)  # found on the 2nd check


class MaxRecordsPerBatchTests(unittest.TestCase):
    def test_exceeding_limit_fails_the_batch_without_silent_truncation(self):
        client = FakeWorkflowClient()
        config = WorkflowSinkConfig(
            name='order_actions',
            workflow='process_order',
            id_field='order_id',
            max_in_flight=1,
            max_records_per_batch=2,
        )
        handler = DaprWorkflowBatchHandler(config, workflow_client=client)
        batch = FakeDataFrame([_order_row(1), _order_row(2), _order_row(3)])

        with self.assertRaises(DaprDatabricksSinkError) as ctx:
            handler.process(batch, batch_id=1)

        self.assertIn('max_records_per_batch', str(ctx.exception))
        # Already-submitted records before the cap was hit are still durably
        # scheduled; we fail loudly rather than silently dropping record 3.
        self.assertEqual(len(client.scheduled), 2)


class MetadataWrappingTests(unittest.TestCase):
    def test_metadata_enabled_wraps_data_and_metadata(self):
        client = FakeWorkflowClient()
        config = WorkflowSinkConfig(
            name='order_actions',
            workflow='process_order',
            id_field='order_id',
            namespace='orders',
            generation='v2',
            metadata=True,
        )
        handler = DaprWorkflowBatchHandler(config, workflow_client=client)

        handler.process(FakeDataFrame([_order_row(123)]), batch_id=7)

        _, _, payload = client.scheduled[0]
        self.assertEqual(set(payload.keys()), {'data', 'metadata'})
        self.assertEqual(
            payload['metadata'],
            {
                'sink': 'order_actions',
                'workflow': 'process_order',
                'batch_id': 7,
                'namespace': 'orders',
                'generation': 'v2',
            },
        )

    def test_metadata_disabled_sends_raw_mapped_row(self):
        client = FakeWorkflowClient()
        config = WorkflowSinkConfig(
            name='order_actions', workflow='process_order', id_field='order_id', metadata=False
        )
        handler = DaprWorkflowBatchHandler(config, workflow_client=client)

        handler.process(FakeDataFrame([_order_row(123)]), batch_id=1)

        _, _, payload = client.scheduled[0]
        self.assertEqual(payload, {'order_id': 123, 'customer_id': 1, 'status': 'READY'})


class InputMapperTests(unittest.TestCase):
    def test_custom_input_mapper_is_used(self):
        client = FakeWorkflowClient()
        config = WorkflowSinkConfig(
            name='customer_actions',
            workflow='process_customer',
            id_field='customer_id',
            input_mapper=lambda row: {'customer': row['customer_id'], 'status': row['status']},
            metadata=False,
        )
        handler = DaprWorkflowBatchHandler(config, workflow_client=client)
        row = FakeRow(customer_id=456, status='ACTIVE', internal_field='secret')

        handler.process(FakeDataFrame([row]), batch_id=1)

        _, _, payload = client.scheduled[0]
        self.assertEqual(payload, {'customer': 456, 'status': 'ACTIVE'})


class MalformedInputTests(unittest.TestCase):
    def test_missing_business_key_field_fails_the_batch(self):
        client = FakeWorkflowClient()
        config = WorkflowSinkConfig(name='orders', workflow='process_order', id_field='order_id')
        handler = DaprWorkflowBatchHandler(config, workflow_client=client)
        row = FakeRow(customer_id=1)  # no order_id

        with self.assertRaises(DaprDatabricksSinkError):
            handler.process(FakeDataFrame([row]), batch_id=1)

        self.assertEqual(client.scheduled, [])


class BoundedConcurrencyTests(unittest.TestCase):
    def test_never_exceeds_max_in_flight_concurrent_schedule_calls(self):
        max_in_flight = 3
        lock = threading.Lock()
        state = {'current': 0, 'peak': 0}

        class SlowWorkflowClient(FakeWorkflowClient):
            def schedule_new_workflow(self, workflow, **kwargs):
                with lock:
                    state['current'] += 1
                    state['peak'] = max(state['peak'], state['current'])
                time.sleep(0.05)
                try:
                    return super().schedule_new_workflow(workflow, **kwargs)
                finally:
                    with lock:
                        state['current'] -= 1

        client = SlowWorkflowClient()
        config = WorkflowSinkConfig(
            name='order_actions',
            workflow='process_order',
            id_field='order_id',
            max_in_flight=max_in_flight,
        )
        handler = DaprWorkflowBatchHandler(config, workflow_client=client)
        rows = [_order_row(i) for i in range(12)]

        handler.process(FakeDataFrame(rows), batch_id=1)

        self.assertEqual(len(client.scheduled), 12)
        self.assertLessEqual(state['peak'], max_in_flight)
        self.assertGreater(
            state['peak'], 1
        )  # actually exercised concurrency, not accidentally serial


# The exact text a real Databricks serverless / Spark Connect-backed compute
# raised from `df.toLocalIterator()` itself during live end-to-end testing —
# see dapr/ext/databricks/AGENTS.md for the full story.
_TO_LOCAL_ITERATOR_UNSUPPORTED = Exception(
    'toLocalIterator() is not supported when using file-based collect'
)


class ToLocalIteratorFallbackTests(unittest.TestCase):
    """Covers DaprWorkflowBatchHandler._iter_rows falling back to collect()
    on compute where toLocalIterator() itself is unavailable."""

    def test_falls_back_to_collect_and_still_schedules_every_row(self):
        client = FakeWorkflowClient()
        config = WorkflowSinkConfig(name='orders', workflow='process_order', id_field='order_id')
        handler = DaprWorkflowBatchHandler(config, workflow_client=client)
        batch = FakeDataFrame(
            [_order_row(1), _order_row(2)],
            to_local_iterator_error=_TO_LOCAL_ITERATOR_UNSUPPORTED,
        )

        handler.process(batch, batch_id=1)

        self.assertEqual(len(client.scheduled), 2)

    def test_fallback_still_enforces_max_records_per_batch(self):
        client = FakeWorkflowClient()
        config = WorkflowSinkConfig(
            name='orders',
            workflow='process_order',
            id_field='order_id',
            max_in_flight=1,
            max_records_per_batch=2,
        )
        handler = DaprWorkflowBatchHandler(config, workflow_client=client)
        batch = FakeDataFrame(
            [_order_row(1), _order_row(2), _order_row(3)],
            to_local_iterator_error=_TO_LOCAL_ITERATOR_UNSUPPORTED,
        )

        with self.assertRaises(DaprDatabricksSinkError) as ctx:
            handler.process(batch, batch_id=1)

        self.assertIn('max_records_per_batch', str(ctx.exception))
        self.assertEqual(len(client.scheduled), 2)  # bounded, not all 3

    def test_unrelated_to_local_iterator_failure_is_not_swallowed(self):
        client = FakeWorkflowClient()
        config = WorkflowSinkConfig(name='orders', workflow='process_order', id_field='order_id')
        handler = DaprWorkflowBatchHandler(config, workflow_client=client)
        batch = FakeDataFrame(
            [_order_row(1)],
            to_local_iterator_error=RuntimeError('source table permission denied'),
        )

        with self.assertRaises(RuntimeError):
            handler.process(batch, batch_id=1)

        self.assertEqual(client.scheduled, [])


if __name__ == '__main__':
    unittest.main()
