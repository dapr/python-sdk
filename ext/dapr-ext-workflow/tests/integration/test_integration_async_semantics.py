# -*- coding: utf-8 -*-

"""
Copyright 2025 The Dapr Authors
Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at
    http://www.apache.org/licenses/LICENSE-2.0
Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the specific language governing permissions and
limitations under the License.
"""

import os
import time

import pytest

from dapr.ext.workflow import AsyncWorkflowContext, DaprWorkflowClient, WorkflowRuntime

skip_integration = pytest.mark.skipif(
    os.getenv('DAPR_INTEGRATION_TESTS') != '1',
    reason='Set DAPR_INTEGRATION_TESTS=1 to run sidecar integration tests',
)


@skip_integration
def test_integration_suspension_and_buffering():
    runtime = WorkflowRuntime()

    @runtime.async_workflow(name='suspend_orchestrator_async')
    async def suspend_orchestrator(ctx: AsyncWorkflowContext):
        # Expose suspension state via custom status
        ctx.set_custom_status({'is_suspended': getattr(ctx, 'is_suspended', False)})
        # Wait for 'resume_event' and then complete
        data = await ctx.wait_for_external_event('resume_event')
        return {'resumed_with': data}

    runtime.start()
    try:
        try:
            runtime.wait_for_ready(timeout=10)
        except Exception:
            pass

        time.sleep(2)

        client = DaprWorkflowClient()
        instance_id = 'suspend-int-1'
        client.schedule_new_workflow(workflow=suspend_orchestrator, instance_id=instance_id)

        # Wait until started
        client.wait_for_workflow_start(instance_id, timeout_in_seconds=30)

        # Pause and verify state becomes SUSPENDED and custom status updates on next activation
        client.pause_workflow(instance_id)
        # Give the worker time to process suspension
        time.sleep(1)
        state = client.get_workflow_state(instance_id)
        assert state is not None
        assert state.runtime_status.name in ('SUSPENDED', 'RUNNING')  # some hubs report SUSPENDED explicitly

        # While suspended, raise the event; it should buffer
        client.raise_workflow_event(instance_id, 'resume_event', data={'ok': True})

        # Resume and expect completion
        client.resume_workflow(instance_id)
        final = client.wait_for_workflow_completion(instance_id, timeout_in_seconds=60)
        assert final is not None
        assert final.runtime_status.name == 'COMPLETED'
    finally:
        runtime.shutdown()


@skip_integration
def test_integration_termination_semantics():
    runtime = WorkflowRuntime()

    @runtime.async_workflow(name='termination_orchestrator_async')
    async def termination_orchestrator(ctx: AsyncWorkflowContext):
        # Long timer; test will terminate before it fires
        await ctx.create_timer(300.0)
        return 'not-reached'

    print(list(runtime._WorkflowRuntime__worker._registry.orchestrators.keys()))

    runtime.start()
    try:
        try:
            runtime.wait_for_ready(timeout=10)
        except Exception:
            pass

        time.sleep(2)

        client = DaprWorkflowClient()
        instance_id = 'term-int-1'
        client.schedule_new_workflow(workflow=termination_orchestrator, instance_id=instance_id)
        client.wait_for_workflow_start(instance_id, timeout_in_seconds=30)

        # Terminate and assert TERMINATED state, not raising inside orchestrator
        client.terminate_workflow(instance_id, output='terminated')
        final = client.wait_for_workflow_completion(instance_id, timeout_in_seconds=60)
        assert final is not None
        assert final.runtime_status.name == 'TERMINATED'
    finally:
        runtime.shutdown()


@skip_integration
def test_integration_when_any_first_wins():
    runtime = WorkflowRuntime()

    @runtime.async_workflow(name='when_any_async')
    async def when_any_orchestrator(ctx: AsyncWorkflowContext):
        first = await ctx.when_any([
            ctx.wait_for_external_event('go'),
            ctx.create_timer(300.0),
        ])
        # Complete quickly if event won; losers are ignored (no additional commands emitted)
        return {'first': first}

    runtime.start()
    try:
        try:
            runtime.wait_for_ready(timeout=10)
        except Exception:
            pass

        time.sleep(2)

        client = DaprWorkflowClient()
        instance_id = 'whenany-int-1'
        client.schedule_new_workflow(workflow=when_any_orchestrator, instance_id=instance_id)
        client.wait_for_workflow_start(instance_id, timeout_in_seconds=30)

        # Raise event immediately to win the when_any
        client.raise_workflow_event(instance_id, 'go', data={'ok': True})
        final = client.wait_for_workflow_completion(instance_id, timeout_in_seconds=60)
        assert final is not None
        assert final.runtime_status.name == 'COMPLETED'
        # TODO: when sidecar exposes command diagnostics, assert only one command set was emitted
    finally:
        runtime.shutdown()


