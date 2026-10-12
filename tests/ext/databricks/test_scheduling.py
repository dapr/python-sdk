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
from concurrent.futures import ThreadPoolExecutor

import grpc

from dapr.ext.databricks.scheduling import ensure_workflow_scheduled, is_duplicate_instance_error
from tests.ext.databricks._fakes import (
    BarrierSyncedWorkflowClient,
    FakeWorkflowClient,
    SimulatedRpcError,
)


class IsDuplicateInstanceErrorTests(unittest.TestCase):
    def test_true_for_already_exists_status_code(self):
        error = SimulatedRpcError(grpc.StatusCode.ALREADY_EXISTS, 'irrelevant message')
        self.assertTrue(is_duplicate_instance_error(error))

    def test_true_for_message_text_regardless_of_code(self):
        error = SimulatedRpcError(
            grpc.StatusCode.FAILED_PRECONDITION,
            'a workflow with the given instance ID already exists and is not yet reusable',
        )
        self.assertTrue(is_duplicate_instance_error(error))

    def test_false_for_unrelated_error(self):
        error = SimulatedRpcError(grpc.StatusCode.UNAVAILABLE, 'connection refused')
        self.assertFalse(is_duplicate_instance_error(error))


class EnsureWorkflowScheduledTests(unittest.TestCase):
    def test_new_instance_is_scheduled(self):
        client = FakeWorkflowClient()

        outcome = ensure_workflow_scheduled(client, 'process_order', 'orders-1', {'order_id': 1})

        self.assertTrue(outcome.newly_scheduled)
        self.assertEqual(outcome.instance_id, 'orders-1')
        self.assertEqual(client.scheduled, [('process_order', 'orders-1', {'order_id': 1})])
        self.assertEqual(client.get_state_calls, ['orders-1'])

    def test_existing_instance_is_not_rescheduled(self):
        client = FakeWorkflowClient()
        client.existing.add('orders-1')

        outcome = ensure_workflow_scheduled(client, 'process_order', 'orders-1', {'order_id': 1})

        self.assertFalse(outcome.newly_scheduled)
        self.assertEqual(client.scheduled, [])
        self.assertEqual(client.schedule_calls, [])

    def test_lost_response_then_retry_finds_existing_instance(self):
        """schedule succeeds durably server-side, but this attempt sees an error;
        a later retry's existence check must find it and must not reschedule."""
        client = FakeWorkflowClient()
        client.raise_on_schedule['orders-1'] = SimulatedRpcError(
            grpc.StatusCode.DEADLINE_EXCEEDED, 'deadline exceeded'
        )
        client.lost_response_for.add('orders-1')

        with self.assertRaises(grpc.RpcError):
            ensure_workflow_scheduled(client, 'process_order', 'orders-1', {'order_id': 1})

        # Dapr durably accepted it despite the client-visible failure above.
        self.assertIn('orders-1', client.existing)
        self.assertEqual(client.scheduled, [])  # this attempt never observed success

        retry_outcome = ensure_workflow_scheduled(
            client, 'process_order', 'orders-1', {'order_id': 1}
        )

        self.assertFalse(retry_outcome.newly_scheduled)
        self.assertEqual(client.schedule_calls, ['orders-1'])  # no second schedule call

    def test_non_duplicate_schedule_error_propagates(self):
        client = FakeWorkflowClient()
        client.raise_on_schedule['orders-1'] = SimulatedRpcError(
            grpc.StatusCode.UNAUTHENTICATED, 'invalid api token'
        )

        with self.assertRaises(grpc.RpcError):
            ensure_workflow_scheduled(client, 'process_order', 'orders-1', {'order_id': 1})

    def test_get_workflow_state_error_propagates_without_scheduling(self):
        client = FakeWorkflowClient()
        client.raise_on_get_state['orders-1'] = SimulatedRpcError(
            grpc.StatusCode.UNAVAILABLE, 'dapr sidecar unavailable'
        )

        with self.assertRaises(grpc.RpcError):
            ensure_workflow_scheduled(client, 'process_order', 'orders-1', {'order_id': 1})

        self.assertEqual(client.scheduled, [])
        self.assertEqual(client.schedule_calls, [])

    def test_concurrent_race_resolves_to_exactly_one_new_and_rest_existing(self):
        party_count = 2
        client = BarrierSyncedWorkflowClient(party_count=party_count)

        with ThreadPoolExecutor(max_workers=party_count) as pool:
            futures = [
                pool.submit(
                    ensure_workflow_scheduled, client, 'process_order', 'orders-1', {'order_id': 1}
                )
                for _ in range(party_count)
            ]
            outcomes = [future.result() for future in futures]

        newly_scheduled_count = sum(1 for outcome in outcomes if outcome.newly_scheduled)
        self.assertEqual(newly_scheduled_count, 1)
        self.assertEqual(len(outcomes) - newly_scheduled_count, party_count - 1)
        for outcome in outcomes:
            self.assertEqual(outcome.instance_id, 'orders-1')
        self.assertEqual(client.scheduled, [('process_order', 'orders-1', {'order_id': 1})])


if __name__ == '__main__':
    unittest.main()
