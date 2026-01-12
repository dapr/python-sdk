# -*- coding: utf-8 -*-

"""
E2E tests for cross-app workflow interceptors.

These tests require multiple Dapr sidecars to be running.
Run with: pytest -m e2e tests/integration/test_cross_app_interceptors_e2e.py
"""

from __future__ import annotations

import multiprocessing
import time
from dataclasses import replace
from datetime import timedelta

import pytest
from dapr.ext.workflow import (
    BaseWorkflowOutboundInterceptor,
    CallActivityRequest,
    DaprWorkflowClient,
    RetryPolicy,
    WorkflowRuntime,
)

from .dapr_test_utils import dapr_sidecar_fixture, skip_if_no_dapr

pytestmark = [pytest.mark.e2e, skip_if_no_dapr]

# Configuration for test apps
app1 = {
    'id': 'cross-app-test-app1',
    'grpc_port': 50101,
    'http_port': 3101,
}
app2 = {
    'id': 'cross-app-test-app2',
    'grpc_port': 50102,
    'http_port': 3102,
}


@pytest.fixture(scope='module')
def dapr_app1_sidecar():
    """Start dapr sidecar for app1."""
    yield from dapr_sidecar_fixture(app1['id'], app1['grpc_port'], app1['http_port'])


@pytest.fixture(scope='module')
def dapr_app2_sidecar():
    """Start dapr sidecar for app2."""
    yield from dapr_sidecar_fixture(app2['id'], app2['grpc_port'], app2['http_port'])


def _run_app2_worker(retry_count: multiprocessing.Value):
    """Run app2 workflow worker (activity provider)."""
    print('[App2 Worker] Starting...', flush=True)
    runtime = WorkflowRuntime(host='127.0.0.1', port=str(app2['grpc_port']))

    @runtime.activity(name='remote_activity')
    def remote_activity(ctx, input_data):
        retry_count.value += 1  # only one process can access this value so no need to lock
        print(
            f'[App2 Worker] remote_activity called (attempt {retry_count.value}) with: {input_data}',
            flush=True,
        )

        # Fail first 2 attempts to test retry policy
        if retry_count.value <= 2:
            print(f'[App2 Worker] Simulating failure on attempt {retry_count.value}', flush=True)
            raise Exception(f'Simulated failure on attempt {retry_count.value}')

        print(f'[App2 Worker] Success on attempt {retry_count.value}', flush=True)
        return f'remote-result-{input_data}'

    print('[App2 Worker] Starting runtime...', flush=True)
    runtime.start()
    print('[App2 Worker] Runtime started, waiting for work...', flush=True)

    # Keep running until parent terminates us
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        pass
    finally:
        print(f'[App2 Worker] Final retry count: {retry_count.value}', flush=True)
        print('[App2 Worker] Shutting down...', flush=True)
        runtime.shutdown()


def test_cross_app_interceptor_modifies_retry_policy(dapr_app1_sidecar, dapr_app2_sidecar):
    """Test that interceptors can modify retry_policy for cross-app activity calls.

    This test requires two Dapr sidecars:
    - app1: Runs workflow with interceptor that sets retry policy
    - app2: Provides the remote activity
    """
    print('\n[Test] Starting app2 worker process...', flush=True)
    retry_count = multiprocessing.Manager().Value('i', 0)  # type: ignore
    # Start app2 worker in background process
    app2_process = multiprocessing.Process(target=_run_app2_worker, args=(retry_count,))
    app2_process.start()

    try:
        # Give app2 worker time to start and register activities
        print('[Test] Waiting for app2 worker to register activities...', flush=True)
        time.sleep(10)

        # Track interceptor calls
        interceptor_calls = []

        class TestRetryInterceptor(BaseWorkflowOutboundInterceptor):
            def call_activity(self, request: CallActivityRequest, next):
                print(
                    f'[Test] Interceptor called: {request.activity_name}, app_id={request.app_id}',
                    flush=True,
                )
                # Record the call
                interceptor_calls.append(
                    {
                        'activity_name': request.activity_name,
                        'app_id': request.app_id,
                        'had_retry_policy': request.retry_policy is not None,
                    }
                )

                # Add retry policy if none exists
                retry_policy = request.retry_policy
                if retry_policy is None:
                    retry_policy = RetryPolicy(
                        max_number_of_attempts=3,
                        first_retry_interval=timedelta(milliseconds=100),
                        max_retry_interval=timedelta(seconds=2),
                    )

                return next(replace(request, retry_policy=retry_policy))

        print('[Test] Creating app1 runtime with interceptor...', flush=True)
        runtime = WorkflowRuntime(
            host='127.0.0.1',
            port=str(app1['grpc_port']),
            workflow_outbound_interceptors=[TestRetryInterceptor()],
        )

        @runtime.workflow(name='cross_app_workflow')
        def cross_app_workflow(ctx, input_data):
            print(f'[Test] Workflow executing with input: {input_data}', flush=True)
            # Call cross-app activity - should go through interceptor
            result = yield ctx.call_activity('remote_activity', input=input_data, app_id=app2['id'])
            print(f'[Test] Workflow got result: {result}', flush=True)
            return result

        print('[Test] Starting app1 runtime...', flush=True)
        runtime.start()
        time.sleep(5)  # Give runtime time to start

        try:
            print('[Test] Creating workflow client...', flush=True)
            client = DaprWorkflowClient(host='127.0.0.1', port=str(app1['grpc_port']))
            instance_id = f'test-cross-app-{int(time.time())}'

            print(f'[Test] Scheduling workflow with instance_id: {instance_id}', flush=True)
            # Schedule and run workflow
            client.schedule_new_workflow(
                workflow=cross_app_workflow, instance_id=instance_id, input='test-data'
            )

            print('[Test] Waiting for workflow completion...', flush=True)
            # Wait for completion - should succeed after retries
            state = client.wait_for_workflow_completion(instance_id, timeout_in_seconds=60)

            print(
                f'[Test] Workflow completed with status: {state.runtime_status.name if state else "None"}',
                flush=True,
            )

            # Verify workflow completed successfully (after retries)
            assert state is not None, 'Workflow state should not be None'
            print(f'[Test] Workflow status: {state.runtime_status.name}', flush=True)
            if state.runtime_status.name != 'COMPLETED':
                print(f'[Test] Workflow failed: {state.serialized_output}', flush=True)
            assert state.runtime_status.name == 'COMPLETED', (
                f'Expected COMPLETED but got {state.runtime_status.name}'
            )

            # Verify the workflow result is correct (proves retry succeeded)
            import json

            result = json.loads(state.serialized_output) if state.serialized_output else None
            print(f'[Test] Workflow result: {result}', flush=True)
            assert result == 'remote-result-test-data', (
                f'Expected "remote-result-test-data" but got {result}'
            )

            # Verify interceptor was called
            print(f'[Test] Interceptor calls: {interceptor_calls}', flush=True)
            assert len(interceptor_calls) >= 1, (
                f'Expected at least 1 interceptor call, got {len(interceptor_calls)}'
            )
            assert interceptor_calls[0]['activity_name'] == 'remote_activity'
            assert interceptor_calls[0]['app_id'] == app2['id']
            assert interceptor_calls[0]['had_retry_policy'] is False
            assert retry_count.value == 3, f'Expected retry count to be 3, got {retry_count.value}'

            print('[Test] All assertions passed! Activity succeeded after retries.', flush=True)

        finally:
            print('[Test] Shutting down app1 runtime...', flush=True)
            runtime.shutdown()

    finally:
        # Clean up app2 worker
        print('[Test] Terminating app2 worker...', flush=True)
        app2_process.terminate()
        app2_process.join(timeout=5)
        if app2_process.is_alive():
            print('[Test] Force killing app2 worker...', flush=True)
            app2_process.kill()
            app2_process.join()


if __name__ == '__main__':
    # For manual testing
    pytest.main([__file__, '-v', '-m', 'e2e'])
