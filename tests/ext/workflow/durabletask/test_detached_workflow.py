# Copyright 2026 The Dapr Authors
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#     http://www.apache.org/licenses/LICENSE-2.0
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Tests for detached-workflow support in the vendored durabletask engine.

Detached workflows are fire-and-forget: the caller receives an instance ID
synchronously, no awaitable task is produced, and no completion or failure
flows back. On replay, the caller's history contains a single
DetachedWorkflowInstanceCreatedEvent per spawn that must reconcile against
the CreateDetachedWorkflowAction produced during execution.
"""

import logging
from datetime import datetime, timezone

import dapr.ext.workflow._durabletask.internal.helpers as helpers
import dapr.ext.workflow._durabletask.internal.protos as pb
from dapr.ext.workflow._durabletask import task, worker

logging.basicConfig(level=logging.DEBUG)
TEST_LOGGER = logging.getLogger('tests-detached')

TEST_INSTANCE_ID = 'parent-abc'


def _run(registry: worker._Registry, entry_name: str, encoded_input=None):
    new_events = [
        helpers.new_workflow_started_event(),
        helpers.new_execution_started_event(
            entry_name, TEST_INSTANCE_ID, encoded_input=encoded_input
        ),
    ]
    executor = worker._OrchestrationExecutor(registry, TEST_LOGGER)
    return executor.execute(TEST_INSTANCE_ID, [], new_events)


def test_schedule_new_workflow_produces_detached_action_with_default_id():
    def child(ctx: task.OrchestrationContext, _):
        pass

    def parent(ctx: task.OrchestrationContext, _):
        spawned_id = ctx.schedule_new_workflow(child, input={'x': 1})
        return spawned_id

    registry = worker._Registry()
    child_name = registry.add_orchestrator(child)
    parent_name = registry.add_orchestrator(parent)

    result = _run(registry, parent_name)
    actions = result.actions

    detached_actions = [a for a in actions if a.HasField('createDetachedWorkflow')]
    assert len(detached_actions) == 1
    action = detached_actions[0]
    assert action.createDetachedWorkflow.name == child_name
    assert action.createDetachedWorkflow.instanceId == f'{TEST_INSTANCE_ID}-1'
    assert action.createDetachedWorkflow.input.value == '{"x": 1}'

    complete = [a for a in actions if a.HasField('completeWorkflow')]
    assert len(complete) == 1
    assert complete[0].completeWorkflow.workflowStatus == pb.ORCHESTRATION_STATUS_COMPLETED
    assert complete[0].completeWorkflow.result.value == f'"{TEST_INSTANCE_ID}-1"'


def test_schedule_new_workflow_with_explicit_id_and_app_id():
    def child(ctx: task.OrchestrationContext, _):
        pass

    def parent(ctx: task.OrchestrationContext, _):
        ctx.schedule_new_workflow(
            'child', input=None, instance_id='detached-xyz', app_id='other-app'
        )

    registry = worker._Registry()
    parent_name = registry.add_orchestrator(parent)

    exec_evt = helpers.new_execution_started_event(
        parent_name, TEST_INSTANCE_ID, encoded_input=None
    )
    exec_evt.router.sourceAppID = 'source-app'
    new_events = [helpers.new_workflow_started_event(), exec_evt]

    executor = worker._OrchestrationExecutor(registry, TEST_LOGGER)
    result = executor.execute(TEST_INSTANCE_ID, [], new_events)

    detached_actions = [a for a in result.actions if a.HasField('createDetachedWorkflow')]
    assert len(detached_actions) == 1
    action = detached_actions[0]
    assert action.createDetachedWorkflow.instanceId == 'detached-xyz'
    assert action.createDetachedWorkflow.name == 'child'
    assert action.router.sourceAppID == 'source-app'
    assert action.router.targetAppID == 'other-app'
    assert not action.createDetachedWorkflow.HasField('input')


def test_schedule_new_workflow_does_not_block_completion():
    """The parent must complete in the same execution tick as the spawn."""

    def child(ctx: task.OrchestrationContext, _):
        pass

    def parent(ctx: task.OrchestrationContext, _):
        ctx.schedule_new_workflow(child)
        return 'parent-done'

    registry = worker._Registry()
    registry.add_orchestrator(child)
    parent_name = registry.add_orchestrator(parent)

    result = _run(registry, parent_name)

    action_types = [a.WhichOneof('workflowActionType') for a in result.actions]
    assert 'createDetachedWorkflow' in action_types
    assert 'completeWorkflow' in action_types
    complete = [a for a in result.actions if a.HasField('completeWorkflow')][0]
    assert complete.completeWorkflow.workflowStatus == pb.ORCHESTRATION_STATUS_COMPLETED
    assert complete.completeWorkflow.result.value == '"parent-done"'


def test_detached_event_reconciles_on_replay():
    """A history with DetachedWorkflowInstanceCreatedEvent must replay cleanly.

    We drive the workflow across two executor passes: the first spawns the
    detached workflow and waits on an external event; the second replays the
    recorded detached-created event and unblocks on the external event.
    """

    def child(ctx: task.OrchestrationContext, _):
        pass

    def parent(ctx: task.OrchestrationContext, _):
        ctx.schedule_new_workflow(child)
        yield ctx.wait_for_external_event('go')
        return 'done'

    registry = worker._Registry()
    registry.add_orchestrator(child)
    parent_name = registry.add_orchestrator(parent)

    spawn_id = f'{TEST_INSTANCE_ID}-1'
    old_events = [
        helpers.new_workflow_started_event(),
        helpers.new_execution_started_event(parent_name, TEST_INSTANCE_ID, encoded_input=None),
        helpers.new_detached_workflow_instance_created_event(1, spawn_id),
    ]
    new_events = [helpers.new_event_raised_event('go')]

    executor = worker._OrchestrationExecutor(registry, TEST_LOGGER)
    result = executor.execute(TEST_INSTANCE_ID, old_events, new_events)

    complete = [a for a in result.actions if a.HasField('completeWorkflow')]
    assert len(complete) == 1
    assert complete[0].completeWorkflow.workflowStatus == pb.ORCHESTRATION_STATUS_COMPLETED
    assert complete[0].completeWorkflow.result.value == '"done"'


def test_replay_detects_wrong_instance_id_mismatch():
    """Replaying a history whose recorded instance ID disagrees with the current
    execution should surface a non-determinism error."""

    def child(ctx: task.OrchestrationContext, _):
        pass

    def parent(ctx: task.OrchestrationContext, _):
        ctx.schedule_new_workflow(child, instance_id='current-id')
        yield ctx.wait_for_external_event('go')
        return 'done'

    registry = worker._Registry()
    registry.add_orchestrator(child)
    parent_name = registry.add_orchestrator(parent)

    old_events = [
        helpers.new_workflow_started_event(),
        helpers.new_execution_started_event(parent_name, TEST_INSTANCE_ID, encoded_input=None),
        helpers.new_detached_workflow_instance_created_event(1, 'stale-history-id'),
    ]
    new_events = [helpers.new_event_raised_event('go')]

    executor = worker._OrchestrationExecutor(registry, TEST_LOGGER)
    result = executor.execute(TEST_INSTANCE_ID, old_events, new_events)

    complete = [a for a in result.actions if a.HasField('completeWorkflow')]
    assert len(complete) == 1
    assert complete[0].completeWorkflow.workflowStatus == pb.ORCHESTRATION_STATUS_FAILED
    assert complete[0].completeWorkflow.failureDetails.errorType == 'NonDeterminismError'


def test_schedule_new_workflow_with_start_at_sets_scheduled_start_timestamp():
    start = datetime(2027, 1, 15, 12, 30, 0, tzinfo=timezone.utc)

    def child(ctx: task.OrchestrationContext, _):
        pass

    def parent(ctx: task.OrchestrationContext, _):
        ctx.schedule_new_workflow(child, start_at=start)

    registry = worker._Registry()
    registry.add_orchestrator(child)
    parent_name = registry.add_orchestrator(parent)

    result = _run(registry, parent_name)

    detached_actions = [a for a in result.actions if a.HasField('createDetachedWorkflow')]
    assert len(detached_actions) == 1
    action = detached_actions[0]
    assert action.createDetachedWorkflow.HasField('scheduledStartTimestamp')
    assert (
        action.createDetachedWorkflow.scheduledStartTimestamp.ToDatetime(tzinfo=timezone.utc)
        == start
    )


def test_schedule_new_workflow_with_app_namespace_sets_router():
    def child(ctx: task.OrchestrationContext, _):
        pass

    def parent(ctx: task.OrchestrationContext, _):
        ctx.schedule_new_workflow('child', app_id='other-app', app_namespace='prod')

    registry = worker._Registry()
    parent_name = registry.add_orchestrator(parent)

    result = _run(registry, parent_name)

    detached_actions = [a for a in result.actions if a.HasField('createDetachedWorkflow')]
    assert len(detached_actions) == 1
    action = detached_actions[0]
    assert action.router.targetAppID == 'other-app'
    assert action.router.targetAppNamespace == 'prod'


def test_multiple_detached_spawns_use_sequential_default_ids():
    def child(ctx: task.OrchestrationContext, _):
        pass

    def parent(ctx: task.OrchestrationContext, _):
        for _ in range(3):
            ctx.schedule_new_workflow(child)

    registry = worker._Registry()
    registry.add_orchestrator(child)
    parent_name = registry.add_orchestrator(parent)

    result = _run(registry, parent_name)

    detached_actions = [a for a in result.actions if a.HasField('createDetachedWorkflow')]
    assert len(detached_actions) == 3
    spawned_ids = [a.createDetachedWorkflow.instanceId for a in detached_actions]
    assert spawned_ids == [
        f'{TEST_INSTANCE_ID}-1',
        f'{TEST_INSTANCE_ID}-2',
        f'{TEST_INSTANCE_ID}-3',
    ]
