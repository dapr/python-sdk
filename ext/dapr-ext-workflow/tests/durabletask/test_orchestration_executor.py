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

import json
import logging
from datetime import datetime, timedelta, timezone

import dapr.ext.workflow._durabletask.internal.helpers as helpers
import dapr.ext.workflow._durabletask.internal.protos as pb
import pytest
from dapr.ext.workflow._durabletask import task, worker

logging.basicConfig(
    format='%(asctime)s.%(msecs)03d %(name)s %(levelname)s: %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
    level=logging.DEBUG,
)
TEST_LOGGER = logging.getLogger('tests')

TEST_INSTANCE_ID = 'abc123'


def test_orchestrator_inputs():
    """Validates orchestrator function input population"""

    def orchestrator(ctx: task.OrchestrationContext, my_input: int):
        return my_input, ctx.instance_id, str(ctx.current_utc_datetime), ctx.is_replaying

    test_input = 42

    registry = worker._Registry()
    name = registry.add_orchestrator(orchestrator)

    start_time = datetime.now()
    new_events = [
        helpers.new_workflow_started_event(start_time),
        helpers.new_execution_started_event(
            name, TEST_INSTANCE_ID, encoded_input=json.dumps(test_input)
        ),
    ]
    executor = worker._OrchestrationExecutor(registry, TEST_LOGGER)
    result = executor.execute(TEST_INSTANCE_ID, [], new_events)
    actions = result.actions

    complete_action = get_and_validate_single_complete_workflow_action(actions)
    assert complete_action.workflowStatus == pb.ORCHESTRATION_STATUS_COMPLETED
    assert complete_action.result is not None

    expected_output = [test_input, TEST_INSTANCE_ID, str(start_time), False]
    assert complete_action.result.value == json.dumps(expected_output)


def test_complete_orchestration_actions():
    """Tests the actions output for a completed orchestration"""

    def empty_orchestrator(ctx: task.OrchestrationContext, _):
        return 'done'

    registry = worker._Registry()
    name = registry.add_orchestrator(empty_orchestrator)

    new_events = [helpers.new_execution_started_event(name, TEST_INSTANCE_ID, encoded_input=None)]
    executor = worker._OrchestrationExecutor(registry, TEST_LOGGER)
    result = executor.execute(TEST_INSTANCE_ID, [], new_events)
    actions = result.actions

    complete_action = get_and_validate_single_complete_workflow_action(actions)
    assert complete_action.workflowStatus == pb.ORCHESTRATION_STATUS_COMPLETED
    assert complete_action.result.value == '"done"'  # results are JSON-encoded


def test_orchestrator_not_registered():
    """Tests the effect of scheduling an unregistered orchestrator"""

    registry = worker._Registry()
    name = 'Bogus'
    new_events = [helpers.new_execution_started_event(name, TEST_INSTANCE_ID, encoded_input=None)]
    executor = worker._OrchestrationExecutor(registry, TEST_LOGGER)
    result = executor.execute(TEST_INSTANCE_ID, [], new_events)
    actions = result.actions

    complete_action = get_and_validate_single_complete_workflow_action(actions)
    assert complete_action.workflowStatus == pb.ORCHESTRATION_STATUS_FAILED
    assert complete_action.failureDetails.errorType == 'OrchestratorNotRegisteredError'
    assert complete_action.failureDetails.errorMessage


def test_create_timer_actions():
    """Tests the actions output for the create_timer orchestrator method"""

    def delay_orchestrator(ctx: task.OrchestrationContext, _):
        due_time = ctx.current_utc_datetime + timedelta(seconds=1)
        yield ctx.create_timer(due_time)
        return 'done'

    registry = worker._Registry()
    name = registry.add_orchestrator(delay_orchestrator)

    start_time = datetime(2020, 1, 1, 12, 0, 0)
    expected_fire_at = start_time + timedelta(seconds=1)

    new_events = [
        helpers.new_workflow_started_event(start_time),
        helpers.new_execution_started_event(name, TEST_INSTANCE_ID, encoded_input=None),
    ]
    executor = worker._OrchestrationExecutor(registry, TEST_LOGGER)
    result = executor.execute(TEST_INSTANCE_ID, [], new_events)
    actions = result.actions

    assert actions is not None
    assert len(actions) == 1
    assert type(actions[0]) is pb.WorkflowAction
    assert actions[0].id == 1
    assert actions[0].HasField('createTimer')
    assert actions[0].createTimer.fireAt.ToDatetime() == expected_fire_at


def test_timer_fired_completion():
    """Tests the resumption of task using a timer_fired event"""

    def delay_orchestrator(ctx: task.OrchestrationContext, _):
        due_time = ctx.current_utc_datetime + timedelta(seconds=1)
        yield ctx.create_timer(due_time)
        return 'done'

    registry = worker._Registry()
    name = registry.add_orchestrator(delay_orchestrator)

    start_time = datetime(2020, 1, 1, 12, 0, 0)
    expected_fire_at = start_time + timedelta(seconds=1)

    old_events = [
        helpers.new_workflow_started_event(start_time),
        helpers.new_execution_started_event(name, TEST_INSTANCE_ID, encoded_input=None),
        helpers.new_timer_created_event(1, expected_fire_at),
    ]
    new_events = [helpers.new_timer_fired_event(1, expected_fire_at)]

    executor = worker._OrchestrationExecutor(registry, TEST_LOGGER)
    result = executor.execute(TEST_INSTANCE_ID, old_events, new_events)
    actions = result.actions

    complete_action = get_and_validate_single_complete_workflow_action(actions)
    assert complete_action.workflowStatus == pb.ORCHESTRATION_STATUS_COMPLETED
    assert complete_action.result is not None
    assert complete_action.result.value == '"done"'  # results are JSON-encoded


def test_schedule_activity_actions():
    """Test the actions output for the call_activity orchestrator method"""

    def dummy_activity(ctx, _):
        pass

    def orchestrator(ctx: task.OrchestrationContext, orchestrator_input):
        yield ctx.call_activity(dummy_activity, input=orchestrator_input)

    registry = worker._Registry()
    name = registry.add_orchestrator(orchestrator)

    # TODO: Test several different input types (int, bool, str, dict, etc.)
    encoded_input = json.dumps(42)
    new_events = [
        helpers.new_workflow_started_event(),
        helpers.new_execution_started_event(name, TEST_INSTANCE_ID, encoded_input),
    ]
    executor = worker._OrchestrationExecutor(registry, TEST_LOGGER)
    result = executor.execute(TEST_INSTANCE_ID, [], new_events)
    actions = result.actions

    assert len(actions) == 1
    assert type(actions[0]) is pb.WorkflowAction
    assert actions[0].id == 1
    assert actions[0].HasField('scheduleTask')
    assert actions[0].scheduleTask.name == task.get_name(dummy_activity)
    assert actions[0].scheduleTask.input.value == encoded_input


def test_schedule_activity_actions_router_without_app_id():
    """Tests that scheduleTask action contains correct router fields when app_id is specified"""

    def dummy_activity(ctx, _):
        pass

    def orchestrator(ctx: task.OrchestrationContext, _):
        yield ctx.call_activity(dummy_activity, input=42)

    registry = worker._Registry()
    name = registry.add_orchestrator(orchestrator)

    # Prepare execution started event with source app set on router
    exec_evt = helpers.new_execution_started_event(name, TEST_INSTANCE_ID, encoded_input=None)
    exec_evt.router.sourceAppID = 'source-app'

    new_events = [
        helpers.new_workflow_started_event(),
        exec_evt,
    ]

    executor = worker._OrchestrationExecutor(registry, TEST_LOGGER)
    result = executor.execute(TEST_INSTANCE_ID, [], new_events)
    actions = result.actions

    assert len(actions) == 1
    action = actions[0]
    assert action.router.sourceAppID == 'source-app'
    assert action.router.targetAppID == ''
    assert action.scheduleTask.router.sourceAppID == 'source-app'
    assert action.scheduleTask.router.targetAppID == ''


def test_schedule_activity_actions_router_with_app_id():
    """Tests that scheduleTask action contains correct router fields when app_id is specified"""

    def dummy_activity(ctx, _):
        pass

    def orchestrator(ctx: task.OrchestrationContext, _):
        yield ctx.call_activity(dummy_activity, input=42, app_id='target-app')

    registry = worker._Registry()
    name = registry.add_orchestrator(orchestrator)

    # Prepare execution started event with source app set on router
    exec_evt = helpers.new_execution_started_event(name, TEST_INSTANCE_ID, encoded_input=None)
    exec_evt.router.sourceAppID = 'source-app'

    new_events = [
        helpers.new_workflow_started_event(),
        exec_evt,
    ]

    executor = worker._OrchestrationExecutor(registry, TEST_LOGGER)
    result = executor.execute(TEST_INSTANCE_ID, [], new_events)
    actions = result.actions

    assert len(actions) == 1
    action = actions[0]
    assert action.router.sourceAppID == 'source-app'
    assert action.router.targetAppID == 'target-app'
    assert action.scheduleTask.router.sourceAppID == 'source-app'
    assert action.scheduleTask.router.targetAppID == 'target-app'


def test_activity_task_completion():
    """Tests the successful completion of an activity task"""

    def dummy_activity(ctx, _):
        pass

    def orchestrator(ctx: task.OrchestrationContext, orchestrator_input):
        result = yield ctx.call_activity(dummy_activity, input=orchestrator_input)
        return result

    registry = worker._Registry()
    name = registry.add_orchestrator(orchestrator)

    old_events = [
        helpers.new_workflow_started_event(),
        helpers.new_execution_started_event(name, TEST_INSTANCE_ID, encoded_input=None),
        helpers.new_task_scheduled_event(1, task.get_name(dummy_activity)),
    ]

    encoded_output = json.dumps('done!')
    new_events = [helpers.new_task_completed_event(1, encoded_output)]

    executor = worker._OrchestrationExecutor(registry, TEST_LOGGER)
    result = executor.execute(TEST_INSTANCE_ID, old_events, new_events)
    actions = result.actions

    complete_action = get_and_validate_single_complete_workflow_action(actions)
    assert complete_action.workflowStatus == pb.ORCHESTRATION_STATUS_COMPLETED
    assert complete_action.result.value == encoded_output


def test_activity_task_failed():
    """Tests the failure of an activity task"""

    def dummy_activity(ctx, _):
        pass

    def orchestrator(ctx: task.OrchestrationContext, orchestrator_input):
        result = yield ctx.call_activity(dummy_activity, input=orchestrator_input)
        return result

    registry = worker._Registry()
    name = registry.add_orchestrator(orchestrator)

    old_events = [
        helpers.new_workflow_started_event(),
        helpers.new_execution_started_event(name, TEST_INSTANCE_ID, encoded_input=None),
        helpers.new_task_scheduled_event(1, task.get_name(dummy_activity)),
    ]

    ex = Exception('Kah-BOOOOM!!!')
    new_events = [helpers.new_task_failed_event(1, ex)]

    executor = worker._OrchestrationExecutor(registry, TEST_LOGGER)
    result = executor.execute(TEST_INSTANCE_ID, old_events, new_events)
    actions = result.actions

    complete_action = get_and_validate_single_complete_workflow_action(actions)
    assert complete_action.workflowStatus == pb.ORCHESTRATION_STATUS_FAILED
    assert (
        complete_action.failureDetails.errorType == 'TaskFailedError'
    )  # TODO: Should this be the specific error?
    assert str(ex) in complete_action.failureDetails.errorMessage

    # Make sure the line of code where the exception was raised is included in the stack trace
    user_code_statement = 'ctx.call_activity(dummy_activity, input=orchestrator_input)'
    assert user_code_statement in complete_action.failureDetails.stackTrace.value


def test_activity_retry_policies():
    """Tests the retry policy logic for activity tasks.

    Each retry attempt gets a NEW sequence number (event ID). The
    taskExecutionId remains the same across all retry attempts.

    Sequence of IDs:
      Attempt 1: scheduleTask(id=1)
      Retry timer 1: createTimer(id=2)
      Attempt 2: scheduleTask(id=3)
      Retry timer 2: createTimer(id=4)
      Attempt 3: scheduleTask(id=5)
      ... and so on
    """

    def dummy_activity(ctx, _):
        raise ValueError('Kah-BOOOOM!!!')

    def orchestrator(ctx: task.OrchestrationContext, orchestrator_input):
        result = yield ctx.call_activity(
            dummy_activity,
            retry_policy=task.RetryPolicy(
                first_retry_interval=timedelta(seconds=1),
                max_number_of_attempts=6,
                backoff_coefficient=2,
                max_retry_interval=timedelta(seconds=10),
                retry_timeout=timedelta(seconds=50),
            ),
            input=orchestrator_input,
        )
        return result

    registry = worker._Registry()
    name = registry.add_orchestrator(orchestrator)

    current_timestamp = datetime.utcnow()

    # --- Attempt 1: scheduleTask(id=1) fails ---
    old_events = [
        helpers.new_workflow_started_event(timestamp=current_timestamp),
        helpers.new_execution_started_event(name, TEST_INSTANCE_ID, encoded_input=None),
        helpers.new_task_scheduled_event(1, task.get_name(dummy_activity)),
    ]
    expected_fire_at = current_timestamp + timedelta(seconds=1)

    new_events = [
        helpers.new_workflow_started_event(timestamp=current_timestamp),
        helpers.new_task_failed_event(1, ValueError('Kah-BOOOOM!!!')),
    ]
    executor = worker._OrchestrationExecutor(registry, TEST_LOGGER)
    result = executor.execute(TEST_INSTANCE_ID, old_events, new_events)
    actions = result.actions
    assert len(actions) == 1
    assert actions[0].HasField('createTimer')
    assert actions[0].createTimer.fireAt.ToDatetime() == expected_fire_at
    assert actions[0].id == 2

    # --- Timer fires, retry schedules scheduleTask(id=3) ---
    current_timestamp = expected_fire_at
    old_events = old_events + new_events
    new_events = [
        helpers.new_workflow_started_event(current_timestamp),
        helpers.new_timer_created_event(2, current_timestamp),
        helpers.new_timer_fired_event(2, current_timestamp),
    ]
    executor = worker._OrchestrationExecutor(registry, TEST_LOGGER)
    result = executor.execute(TEST_INSTANCE_ID, old_events, new_events)
    actions = result.actions
    assert len(actions) == 1
    assert actions[0].HasField('scheduleTask')
    assert actions[0].id == 3  # NEW sequence number for retry
    # Capture the taskExecutionId from first retry - it must be non-empty
    # and consistent across ALL retry attempts
    retry_task_execution_id = actions[0].scheduleTask.taskExecutionId
    assert retry_task_execution_id != '', 'taskExecutionId must be non-empty'

    # --- Attempt 2: scheduleTask(id=3) fails ---
    old_events = old_events + new_events
    expected_fire_at = current_timestamp + timedelta(seconds=2)
    new_events = [
        helpers.new_workflow_started_event(current_timestamp),
        helpers.new_task_scheduled_event(3, task.get_name(dummy_activity)),
        helpers.new_task_failed_event(3, ValueError('Kah-BOOOOM!!!')),
    ]
    executor = worker._OrchestrationExecutor(registry, TEST_LOGGER)
    result = executor.execute(TEST_INSTANCE_ID, old_events, new_events)
    actions = result.actions
    assert len(actions) == 1
    assert actions[0].HasField('createTimer')
    assert actions[0].createTimer.fireAt.ToDatetime() == expected_fire_at
    assert actions[0].id == 4

    # --- Timer fires, retry schedules scheduleTask(id=5) ---
    current_timestamp = expected_fire_at
    old_events = old_events + new_events
    new_events = [
        helpers.new_workflow_started_event(current_timestamp),
        helpers.new_timer_created_event(4, current_timestamp),
        helpers.new_timer_fired_event(4, current_timestamp),
    ]
    executor = worker._OrchestrationExecutor(registry, TEST_LOGGER)
    result = executor.execute(TEST_INSTANCE_ID, old_events, new_events)
    actions = result.actions
    assert len(actions) == 1
    assert actions[0].HasField('scheduleTask')
    assert actions[0].id == 5
    assert actions[0].scheduleTask.taskExecutionId == retry_task_execution_id

    # --- Attempt 3: scheduleTask(id=5) fails ---
    expected_fire_at = current_timestamp + timedelta(seconds=4)
    old_events = old_events + new_events
    new_events = [
        helpers.new_workflow_started_event(current_timestamp),
        helpers.new_task_scheduled_event(5, task.get_name(dummy_activity)),
        helpers.new_task_failed_event(5, ValueError('Kah-BOOOOM!!!')),
    ]
    executor = worker._OrchestrationExecutor(registry, TEST_LOGGER)
    result = executor.execute(TEST_INSTANCE_ID, old_events, new_events)
    actions = result.actions
    assert len(actions) == 1
    assert actions[0].HasField('createTimer')
    assert actions[0].createTimer.fireAt.ToDatetime() == expected_fire_at
    assert actions[0].id == 6

    # --- Timer fires, retry schedules scheduleTask(id=7) ---
    current_timestamp = expected_fire_at
    old_events = old_events + new_events
    new_events = [
        helpers.new_workflow_started_event(current_timestamp),
        helpers.new_timer_created_event(6, current_timestamp),
        helpers.new_timer_fired_event(6, current_timestamp),
    ]
    executor = worker._OrchestrationExecutor(registry, TEST_LOGGER)
    result = executor.execute(TEST_INSTANCE_ID, old_events, new_events)
    actions = result.actions
    assert len(actions) == 1
    assert actions[0].HasField('scheduleTask')
    assert actions[0].id == 7
    assert actions[0].scheduleTask.taskExecutionId == retry_task_execution_id

    # --- Attempt 4: scheduleTask(id=7) fails ---
    expected_fire_at = current_timestamp + timedelta(seconds=8)
    old_events = old_events + new_events
    new_events = [
        helpers.new_workflow_started_event(current_timestamp),
        helpers.new_task_scheduled_event(7, task.get_name(dummy_activity)),
        helpers.new_task_failed_event(7, ValueError('Kah-BOOOOM!!!')),
    ]
    executor = worker._OrchestrationExecutor(registry, TEST_LOGGER)
    result = executor.execute(TEST_INSTANCE_ID, old_events, new_events)
    actions = result.actions
    assert len(actions) == 1
    assert actions[0].HasField('createTimer')
    assert actions[0].createTimer.fireAt.ToDatetime() == expected_fire_at
    assert actions[0].id == 8

    # --- Timer fires, retry schedules scheduleTask(id=9) ---
    current_timestamp = expected_fire_at
    old_events = old_events + new_events
    new_events = [
        helpers.new_workflow_started_event(current_timestamp),
        helpers.new_timer_created_event(8, current_timestamp),
        helpers.new_timer_fired_event(8, current_timestamp),
    ]
    executor = worker._OrchestrationExecutor(registry, TEST_LOGGER)
    result = executor.execute(TEST_INSTANCE_ID, old_events, new_events)
    actions = result.actions
    assert len(actions) == 1
    assert actions[0].HasField('scheduleTask')
    assert actions[0].id == 9
    assert actions[0].scheduleTask.taskExecutionId == retry_task_execution_id

    # --- Attempt 5: scheduleTask(id=9) fails ---
    # max_retry_interval caps at 10 seconds (instead of 16)
    expected_fire_at = current_timestamp + timedelta(seconds=10)
    old_events = old_events + new_events
    new_events = [
        helpers.new_workflow_started_event(current_timestamp),
        helpers.new_task_scheduled_event(9, task.get_name(dummy_activity)),
        helpers.new_task_failed_event(9, ValueError('Kah-BOOOOM!!!')),
    ]
    executor = worker._OrchestrationExecutor(registry, TEST_LOGGER)
    result = executor.execute(TEST_INSTANCE_ID, old_events, new_events)
    actions = result.actions
    assert len(actions) == 1
    assert actions[0].HasField('createTimer')
    assert actions[0].createTimer.fireAt.ToDatetime() == expected_fire_at
    assert actions[0].id == 10

    # --- Timer fires, retry schedules scheduleTask(id=11) ---
    current_timestamp = expected_fire_at
    old_events = old_events + new_events
    new_events = [
        helpers.new_workflow_started_event(current_timestamp),
        helpers.new_timer_created_event(10, current_timestamp),
        helpers.new_timer_fired_event(10, current_timestamp),
    ]
    executor = worker._OrchestrationExecutor(registry, TEST_LOGGER)
    result = executor.execute(TEST_INSTANCE_ID, old_events, new_events)
    actions = result.actions
    assert len(actions) == 1
    assert actions[0].HasField('scheduleTask')
    assert actions[0].id == 11
    assert actions[0].scheduleTask.taskExecutionId == retry_task_execution_id

    # --- Attempt 6: scheduleTask(id=11) fails - max attempts exhausted ---
    old_events = old_events + new_events
    new_events = [
        helpers.new_workflow_started_event(current_timestamp),
        helpers.new_task_scheduled_event(11, task.get_name(dummy_activity)),
        helpers.new_task_failed_event(11, ValueError('Kah-BOOOOM!!!')),
    ]
    executor = worker._OrchestrationExecutor(registry, TEST_LOGGER)
    result = executor.execute(TEST_INSTANCE_ID, old_events, new_events)
    actions = result.actions
    assert len(actions) == 1
    assert actions[0].completeWorkflow.failureDetails.errorMessage.__contains__(
        'Activity task #11 failed: Kah-BOOOOM!!!'
    )
    assert actions[0].id == 12


def test_nondeterminism_expected_timer():
    """Tests the non-determinism detection logic when call_timer is expected but some other method (call_activity) is called instead"""

    def dummy_activity(ctx, _):
        pass

    def orchestrator(ctx: task.OrchestrationContext, _):
        result = yield ctx.call_activity(dummy_activity)
        return result

    registry = worker._Registry()
    name = registry.add_orchestrator(orchestrator)

    fire_at = datetime.now()
    old_events = [
        helpers.new_workflow_started_event(),
        helpers.new_execution_started_event(name, TEST_INSTANCE_ID, encoded_input=None),
        helpers.new_timer_created_event(1, fire_at),
    ]
    new_events = [helpers.new_timer_fired_event(timer_id=1, fire_at=fire_at)]

    executor = worker._OrchestrationExecutor(registry, TEST_LOGGER)
    result = executor.execute(TEST_INSTANCE_ID, old_events, new_events)
    actions = result.actions

    complete_action = get_and_validate_single_complete_workflow_action(actions)
    assert complete_action.workflowStatus == pb.ORCHESTRATION_STATUS_FAILED
    assert complete_action.failureDetails.errorType == 'NonDeterminismError'
    assert '1' in complete_action.failureDetails.errorMessage  # task ID
    assert 'create_timer' in complete_action.failureDetails.errorMessage  # expected method name
    assert 'call_activity' in complete_action.failureDetails.errorMessage  # actual method name


def test_nondeterminism_expected_activity_call_no_task_id():
    """Tests the non-determinism detection logic when invoking activity functions"""

    def orchestrator(ctx: task.OrchestrationContext, _):
        result = yield task.CompletableTask()  # dummy task
        return result

    registry = worker._Registry()
    name = registry.add_orchestrator(orchestrator)

    old_events = [
        helpers.new_workflow_started_event(),
        helpers.new_execution_started_event(name, TEST_INSTANCE_ID, encoded_input=None),
        helpers.new_task_scheduled_event(1, 'bogus_activity'),
    ]

    new_events = [helpers.new_task_completed_event(1)]

    executor = worker._OrchestrationExecutor(registry, TEST_LOGGER)
    result = executor.execute(TEST_INSTANCE_ID, old_events, new_events)
    actions = result.actions

    complete_action = get_and_validate_single_complete_workflow_action(actions)
    assert complete_action.workflowStatus == pb.ORCHESTRATION_STATUS_FAILED
    assert complete_action.failureDetails.errorType == 'NonDeterminismError'
    assert '1' in complete_action.failureDetails.errorMessage  # task ID
    assert 'call_activity' in complete_action.failureDetails.errorMessage  # expected method name


def test_nondeterminism_expected_activity_call_wrong_task_type():
    """Tests the non-determinism detection when an activity exists in the history but a non-activity is in the code"""

    def dummy_activity(ctx, _):
        pass

    def orchestrator(ctx: task.OrchestrationContext, _):
        # create a timer when the history expects an activity call
        yield ctx.create_timer(datetime.now())

    registry = worker._Registry()
    name = registry.add_orchestrator(orchestrator)

    old_events = [
        helpers.new_workflow_started_event(),
        helpers.new_execution_started_event(name, TEST_INSTANCE_ID, encoded_input=None),
        helpers.new_task_scheduled_event(1, task.get_name(dummy_activity)),
    ]

    new_events = [helpers.new_task_completed_event(1)]

    executor = worker._OrchestrationExecutor(registry, TEST_LOGGER)
    result = executor.execute(TEST_INSTANCE_ID, old_events, new_events)
    actions = result.actions

    complete_action = get_and_validate_single_complete_workflow_action(actions)
    assert complete_action.workflowStatus == pb.ORCHESTRATION_STATUS_FAILED
    assert complete_action.failureDetails.errorType == 'NonDeterminismError'
    assert '1' in complete_action.failureDetails.errorMessage  # task ID
    assert 'call_activity' in complete_action.failureDetails.errorMessage  # expected method name
    assert 'create_timer' in complete_action.failureDetails.errorMessage  # unexpected method name


def test_nondeterminism_wrong_activity_name():
    """Tests the non-determinism detection when calling an activity with a name that differs from the name in the history"""

    def dummy_activity(ctx, _):
        pass

    def orchestrator(ctx: task.OrchestrationContext, _):
        # create a timer when the history expects an activity call
        yield ctx.call_activity(dummy_activity)

    registry = worker._Registry()
    name = registry.add_orchestrator(orchestrator)

    old_events = [
        helpers.new_workflow_started_event(),
        helpers.new_execution_started_event(name, TEST_INSTANCE_ID, encoded_input=None),
        helpers.new_task_scheduled_event(1, 'original_activity'),
    ]

    new_events = [helpers.new_task_completed_event(1)]

    executor = worker._OrchestrationExecutor(registry, TEST_LOGGER)
    result = executor.execute(TEST_INSTANCE_ID, old_events, new_events)
    actions = result.actions

    complete_action = get_and_validate_single_complete_workflow_action(actions)
    assert complete_action.workflowStatus == pb.ORCHESTRATION_STATUS_FAILED
    assert complete_action.failureDetails.errorType == 'NonDeterminismError'
    assert '1' in complete_action.failureDetails.errorMessage  # task ID
    assert 'call_activity' in complete_action.failureDetails.errorMessage  # expected method name
    assert (
        'original_activity' in complete_action.failureDetails.errorMessage
    )  # expected activity name
    assert (
        'dummy_activity' in complete_action.failureDetails.errorMessage
    )  # unexpected activity name


def test_sub_orchestration_task_completion():
    """Tests that a sub-orchestration task is completed when the sub-orchestration completes"""

    def suborchestrator(ctx: task.OrchestrationContext, _):
        pass

    def orchestrator(ctx: task.OrchestrationContext, _):
        result = yield ctx.call_sub_orchestrator(suborchestrator)
        return result

    registry = worker._Registry()
    suborchestrator_name = registry.add_orchestrator(suborchestrator)
    orchestrator_name = registry.add_orchestrator(orchestrator)

    old_events = [
        helpers.new_workflow_started_event(),
        helpers.new_execution_started_event(
            orchestrator_name, TEST_INSTANCE_ID, encoded_input=None
        ),
        helpers.new_child_workflow_created_event(
            1, suborchestrator_name, 'sub-orch-123', encoded_input=None
        ),
    ]

    new_events = [helpers.new_child_workflow_completed_event(1, encoded_output='42')]

    executor = worker._OrchestrationExecutor(registry, TEST_LOGGER)
    result = executor.execute(TEST_INSTANCE_ID, old_events, new_events)
    actions = result.actions

    complete_action = get_and_validate_single_complete_workflow_action(actions)
    assert complete_action.workflowStatus == pb.ORCHESTRATION_STATUS_COMPLETED
    assert complete_action.result.value == '42'


def test_create_sub_orchestration_actions_router_without_app_id():
    """Tests that createChildWorkflow action contains correct router fields when app_id is specified"""

    def suborchestrator(ctx: task.OrchestrationContext, _):
        pass

    def orchestrator(ctx: task.OrchestrationContext, _):
        yield ctx.call_sub_orchestrator(suborchestrator, input=None)

    registry = worker._Registry()
    registry.add_orchestrator(suborchestrator)
    orchestrator_name = registry.add_orchestrator(orchestrator)

    exec_evt = helpers.new_execution_started_event(
        orchestrator_name, TEST_INSTANCE_ID, encoded_input=None
    )
    exec_evt.router.sourceAppID = 'source-app'

    new_events = [
        helpers.new_workflow_started_event(),
        exec_evt,
    ]

    executor = worker._OrchestrationExecutor(registry, TEST_LOGGER)
    result = executor.execute(TEST_INSTANCE_ID, [], new_events)
    actions = result.actions

    assert len(actions) == 1
    action = actions[0]
    assert action.router.sourceAppID == 'source-app'
    assert action.router.targetAppID == ''
    assert action.createChildWorkflow.router.sourceAppID == 'source-app'
    assert action.createChildWorkflow.router.targetAppID == ''


def test_create_sub_orchestration_actions_router_with_app_id():
    """Tests that createChildWorkflow action contains correct router fields when app_id is specified"""

    def suborchestrator(ctx: task.OrchestrationContext, _):
        pass

    def orchestrator(ctx: task.OrchestrationContext, _):
        yield ctx.call_sub_orchestrator(suborchestrator, input=None, app_id='target-app')

    registry = worker._Registry()
    registry.add_orchestrator(suborchestrator)
    orchestrator_name = registry.add_orchestrator(orchestrator)

    exec_evt = helpers.new_execution_started_event(
        orchestrator_name, TEST_INSTANCE_ID, encoded_input=None
    )
    exec_evt.router.sourceAppID = 'source-app'

    new_events = [
        helpers.new_workflow_started_event(),
        exec_evt,
    ]

    executor = worker._OrchestrationExecutor(registry, TEST_LOGGER)
    result = executor.execute(TEST_INSTANCE_ID, [], new_events)
    actions = result.actions

    assert len(actions) == 1
    action = actions[0]
    assert action.router.sourceAppID == 'source-app'
    assert action.router.targetAppID == 'target-app'
    assert action.createChildWorkflow.router.sourceAppID == 'source-app'
    assert action.createChildWorkflow.router.targetAppID == 'target-app'


def test_sub_orchestration_task_failed():
    """Tests that a sub-orchestration task is completed when the sub-orchestration fails"""

    def suborchestrator(ctx: task.OrchestrationContext, _):
        pass

    def orchestrator(ctx: task.OrchestrationContext, _):
        result = yield ctx.call_sub_orchestrator(suborchestrator)
        return result

    registry = worker._Registry()
    suborchestrator_name = registry.add_orchestrator(suborchestrator)
    orchestrator_name = registry.add_orchestrator(orchestrator)

    old_events = [
        helpers.new_workflow_started_event(),
        helpers.new_execution_started_event(
            orchestrator_name, TEST_INSTANCE_ID, encoded_input=None
        ),
        helpers.new_child_workflow_created_event(
            1, suborchestrator_name, 'sub-orch-123', encoded_input=None
        ),
    ]

    ex = Exception('Kah-BOOOOM!!!')
    new_events = [helpers.new_child_workflow_failed_event(1, ex)]

    executor = worker._OrchestrationExecutor(registry, TEST_LOGGER)
    result = executor.execute(TEST_INSTANCE_ID, old_events, new_events)
    actions = result.actions

    complete_action = get_and_validate_single_complete_workflow_action(actions)
    assert complete_action.workflowStatus == pb.ORCHESTRATION_STATUS_FAILED
    assert (
        complete_action.failureDetails.errorType == 'TaskFailedError'
    )  # TODO: Should this be the specific error?
    assert str(ex) in complete_action.failureDetails.errorMessage

    # Make sure the line of code where the exception was raised is included in the stack trace
    user_code_statement = 'ctx.call_sub_orchestrator(suborchestrator)'
    assert user_code_statement in complete_action.failureDetails.stackTrace.value


def test_nondeterminism_expected_sub_orchestration_task_completion_no_task():
    """Tests the non-determinism detection when a sub-orchestration action is encounteed when it shouldn't be"""

    def orchestrator(ctx: task.OrchestrationContext, _):
        result = yield task.CompletableTask()  # dummy task
        return result

    registry = worker._Registry()
    orchestrator_name = registry.add_orchestrator(orchestrator)

    old_events = [
        helpers.new_workflow_started_event(),
        helpers.new_execution_started_event(
            orchestrator_name, TEST_INSTANCE_ID, encoded_input=None
        ),
        helpers.new_child_workflow_created_event(
            1, 'some_sub_orchestration', 'sub-orch-123', encoded_input=None
        ),
    ]

    new_events = [helpers.new_child_workflow_completed_event(1, encoded_output='42')]

    executor = worker._OrchestrationExecutor(registry, TEST_LOGGER)
    result = executor.execute(TEST_INSTANCE_ID, old_events, new_events)
    actions = result.actions

    complete_action = get_and_validate_single_complete_workflow_action(actions)
    assert complete_action.workflowStatus == pb.ORCHESTRATION_STATUS_FAILED
    assert complete_action.failureDetails.errorType == 'NonDeterminismError'
    assert '1' in complete_action.failureDetails.errorMessage  # task ID
    assert (
        'call_sub_orchestrator' in complete_action.failureDetails.errorMessage
    )  # expected method name


def test_nondeterminism_expected_sub_orchestration_task_completion_wrong_task_type():
    """Tests the non-determinism detection when a sub-orchestration action is encounteed when it shouldn't be.
    This variation tests the case where the expected task type is wrong (e.g. the code schedules a timer task
    but the history contains a sub-orchestration completed task)."""

    def orchestrator(ctx: task.OrchestrationContext, _):
        result = yield ctx.create_timer(
            datetime.now(timezone.utc)
        )  # created timer but history expects sub-orchestration
        return result

    registry = worker._Registry()
    orchestrator_name = registry.add_orchestrator(orchestrator)

    old_events = [
        helpers.new_workflow_started_event(),
        helpers.new_execution_started_event(
            orchestrator_name, TEST_INSTANCE_ID, encoded_input=None
        ),
        helpers.new_child_workflow_created_event(
            1, 'some_sub_orchestration', 'sub-orch-123', encoded_input=None
        ),
    ]

    new_events = [helpers.new_child_workflow_completed_event(1, encoded_output='42')]

    executor = worker._OrchestrationExecutor(registry, TEST_LOGGER)
    result = executor.execute(TEST_INSTANCE_ID, old_events, new_events)
    actions = result.actions

    complete_action = get_and_validate_single_complete_workflow_action(actions)
    assert complete_action.workflowStatus == pb.ORCHESTRATION_STATUS_FAILED
    assert complete_action.failureDetails.errorType == 'NonDeterminismError'
    assert '1' in complete_action.failureDetails.errorMessage  # task ID
    assert (
        'call_sub_orchestrator' in complete_action.failureDetails.errorMessage
    )  # expected method name


def test_raise_event():
    """Tests that an orchestration can wait for and process an external event sent by a client"""

    def orchestrator(ctx: task.OrchestrationContext, _):
        result = yield ctx.wait_for_external_event('my_event')
        return result

    registry = worker._Registry()
    orchestrator_name = registry.add_orchestrator(orchestrator)

    old_events = []
    new_events = [
        helpers.new_workflow_started_event(),
        helpers.new_execution_started_event(orchestrator_name, TEST_INSTANCE_ID),
    ]

    # Execute the orchestration until it is waiting for an external event. An
    # optional TimerOriginExternalEvent timer is scheduled (sentinel fireAt).
    executor = worker._OrchestrationExecutor(registry, TEST_LOGGER)
    result = executor.execute(TEST_INSTANCE_ID, old_events, new_events)
    actions = result.actions
    assert len(actions) == 1
    assert actions[0].HasField('createTimer')

    # Post-patch replay: history contains the matching optional TimerCreated. The
    # orchestration completes normally on event arrival.
    old_events = new_events + [
        helpers.new_timer_created_event(
            1,
            helpers.OPTIONAL_TIMER_FIRE_AT,
            origin=pb.TimerOriginExternalEvent(name='my_event'),
        )
    ]
    new_events = [helpers.new_event_raised_event('my_event', encoded_input='42')]
    executor = worker._OrchestrationExecutor(registry, TEST_LOGGER)
    result = executor.execute(TEST_INSTANCE_ID, old_events, new_events)
    actions = result.actions
    complete_action = get_and_validate_single_complete_workflow_action(actions)
    assert complete_action.workflowStatus == pb.ORCHESTRATION_STATUS_COMPLETED
    assert complete_action.result.value == '42'


def test_raise_event_buffered():
    """Tests that an orchestration can receive an event that arrives earlier than expected"""

    def orchestrator(ctx: task.OrchestrationContext, _):
        yield ctx.create_timer(ctx.current_utc_datetime + timedelta(days=1))
        result = yield ctx.wait_for_external_event('my_event')
        return result

    registry = worker._Registry()
    orchestrator_name = registry.add_orchestrator(orchestrator)

    old_events = []
    new_events = [
        helpers.new_workflow_started_event(),
        helpers.new_execution_started_event(orchestrator_name, TEST_INSTANCE_ID),
        helpers.new_event_raised_event('my_event', encoded_input='42'),
    ]

    # Execute the orchestration. It should be in a running state waiting for the timer to fire
    executor = worker._OrchestrationExecutor(registry, TEST_LOGGER)
    result = executor.execute(TEST_INSTANCE_ID, old_events, new_events)
    actions = result.actions
    assert len(actions) == 1
    assert actions[0].HasField('createTimer')

    # Complete the timer task. The orchestration should move to the wait_for_external_event step, which
    # should then complete immediately because the event was buffered in the old event history.
    timer_due_time = datetime.now(timezone.utc) + timedelta(days=1)
    old_events = new_events + [helpers.new_timer_created_event(1, timer_due_time)]
    new_events = [helpers.new_timer_fired_event(1, timer_due_time)]
    executor = worker._OrchestrationExecutor(registry, TEST_LOGGER)
    result = executor.execute(TEST_INSTANCE_ID, old_events, new_events)
    actions = result.actions
    complete_action = get_and_validate_single_complete_workflow_action(actions)
    assert complete_action.workflowStatus == pb.ORCHESTRATION_STATUS_COMPLETED
    assert complete_action.result.value == '42'


def test_suspend_resume():
    """Tests that an orchestration can be suspended and resumed"""

    def orchestrator(ctx: task.OrchestrationContext, _):
        result = yield ctx.wait_for_external_event('my_event')
        return result

    registry = worker._Registry()
    orchestrator_name = registry.add_orchestrator(orchestrator)

    old_events = [
        helpers.new_workflow_started_event(),
        helpers.new_execution_started_event(orchestrator_name, TEST_INSTANCE_ID),
        # The external event wait creates an optional TimerOriginExternalEvent timer
        # with the sentinel fireAt. Post-patch history contains the matching event.
        helpers.new_timer_created_event(
            1,
            helpers.OPTIONAL_TIMER_FIRE_AT,
            origin=pb.TimerOriginExternalEvent(name='my_event'),
        ),
    ]
    new_events = [
        helpers.new_suspend_event(),
        helpers.new_event_raised_event('my_event', encoded_input='42'),
    ]

    # Execute the orchestration. It should remain in a running state because it was suspended prior
    # to processing the event raised event.
    executor = worker._OrchestrationExecutor(registry, TEST_LOGGER)
    result = executor.execute(TEST_INSTANCE_ID, old_events, new_events)
    actions = result.actions
    assert len(actions) == 0

    # Resume the orchestration. It should complete successfully.
    old_events = old_events + new_events
    new_events = [helpers.new_resume_event()]
    executor = worker._OrchestrationExecutor(registry, TEST_LOGGER)
    result = executor.execute(TEST_INSTANCE_ID, old_events, new_events)
    actions = result.actions
    complete_action = get_and_validate_single_complete_workflow_action(actions)
    assert complete_action.workflowStatus == pb.ORCHESTRATION_STATUS_COMPLETED
    assert complete_action.result.value == '42'


def test_terminate():
    """Tests that an orchestration can be terminated before it completes"""

    def orchestrator(ctx: task.OrchestrationContext, _):
        result = yield ctx.wait_for_external_event('my_event')
        return result

    registry = worker._Registry()
    orchestrator_name = registry.add_orchestrator(orchestrator)

    old_events = [
        helpers.new_workflow_started_event(),
        helpers.new_execution_started_event(orchestrator_name, TEST_INSTANCE_ID),
    ]
    new_events = [
        helpers.new_terminated_event(encoded_output=json.dumps('terminated!')),
        helpers.new_event_raised_event('my_event', encoded_input='42'),
    ]

    # Execute the orchestration. It should be in a running state waiting for an external event
    executor = worker._OrchestrationExecutor(registry, TEST_LOGGER)
    result = executor.execute(TEST_INSTANCE_ID, old_events, new_events)
    actions = result.actions
    complete_action = get_and_validate_single_complete_workflow_action(actions)
    assert complete_action.workflowStatus == pb.ORCHESTRATION_STATUS_TERMINATED
    assert complete_action.result.value == json.dumps('terminated!')


@pytest.mark.parametrize('save_events', [True, False])
def test_continue_as_new(save_events: bool):
    """Tests the behavior of the continue-as-new API"""

    def orchestrator(ctx: task.OrchestrationContext, input: int):
        yield ctx.create_timer(ctx.current_utc_datetime + timedelta(days=1))
        ctx.continue_as_new(input + 1, save_events=save_events)

    registry = worker._Registry()
    orchestrator_name = registry.add_orchestrator(orchestrator)

    old_events = [
        helpers.new_workflow_started_event(),
        helpers.new_execution_started_event(orchestrator_name, TEST_INSTANCE_ID, encoded_input='1'),
        helpers.new_event_raised_event('my_event', encoded_input='42'),
        helpers.new_event_raised_event('my_event', encoded_input='43'),
        helpers.new_event_raised_event('my_event', encoded_input='44'),
        helpers.new_timer_created_event(1, datetime.now(timezone.utc) + timedelta(days=1)),
    ]
    new_events = [helpers.new_timer_fired_event(1, datetime.now(timezone.utc) + timedelta(days=1))]

    # Execute the orchestration. It should be in a running state waiting for the timer to fire
    executor = worker._OrchestrationExecutor(registry, TEST_LOGGER)
    result = executor.execute(TEST_INSTANCE_ID, old_events, new_events)
    actions = result.actions
    complete_action = get_and_validate_single_complete_workflow_action(actions)
    assert complete_action.workflowStatus == pb.ORCHESTRATION_STATUS_CONTINUED_AS_NEW
    assert complete_action.result.value == json.dumps(2)
    assert len(complete_action.carryoverEvents) == (3 if save_events else 0)
    for i in range(len(complete_action.carryoverEvents)):
        event = complete_action.carryoverEvents[i]
        assert type(event) is pb.HistoryEvent
        assert event.HasField('eventRaised')
        assert (
            event.eventRaised.name.casefold() == 'my_event'.casefold()
        )  # event names are case-insensitive
        assert event.eventRaised.input.value == json.dumps(42 + i)


def test_fan_out():
    """Tests that a fan-out pattern correctly schedules N tasks"""

    def hello(_, name: str):
        return f'Hello {name}!'

    def orchestrator(ctx: task.OrchestrationContext, count: int):
        tasks = []
        for i in range(count):
            tasks.append(ctx.call_activity(hello, input=str(i)))
        results = yield task.when_all(tasks)
        return results

    registry = worker._Registry()
    orchestrator_name = registry.add_orchestrator(orchestrator)
    activity_name = registry.add_activity(hello)

    old_events = []
    new_events = [
        helpers.new_workflow_started_event(),
        helpers.new_execution_started_event(
            orchestrator_name, TEST_INSTANCE_ID, encoded_input='10'
        ),
    ]

    executor = worker._OrchestrationExecutor(registry, TEST_LOGGER)
    result = executor.execute(TEST_INSTANCE_ID, old_events, new_events)
    actions = result.actions

    # The result should be 10 "taskScheduled" actions with inputs from 0 to 9
    assert len(actions) == 10
    for i in range(10):
        assert actions[i].HasField('scheduleTask')
        assert actions[i].scheduleTask.name == activity_name
        assert actions[i].scheduleTask.input.value == f'"{i}"'


def test_fan_in():
    """Tests that a fan-in pattern works correctly"""

    def print_int(_, val: int):
        return str(val)

    def orchestrator(ctx: task.OrchestrationContext, _):
        tasks = []
        for i in range(10):
            tasks.append(ctx.call_activity(print_int, input=i))
        results = yield task.when_all(tasks)
        return results

    registry = worker._Registry()
    orchestrator_name = registry.add_orchestrator(orchestrator)
    activity_name = registry.add_activity(print_int)

    old_events = [
        helpers.new_workflow_started_event(),
        helpers.new_execution_started_event(
            orchestrator_name, TEST_INSTANCE_ID, encoded_input=None
        ),
    ]
    for i in range(10):
        old_events.append(
            helpers.new_task_scheduled_event(i + 1, activity_name, encoded_input=str(i))
        )

    new_events = []
    for i in range(10):
        new_events.append(
            helpers.new_task_completed_event(i + 1, encoded_output=print_int(None, i))
        )

    # First, test with only the first 5 events. We expect the orchestration to be running
    # but return zero actions since its still waiting for the other 5 tasks to complete.
    executor = worker._OrchestrationExecutor(registry, TEST_LOGGER)
    result = executor.execute(TEST_INSTANCE_ID, old_events, new_events[:5])
    actions = result.actions
    assert len(actions) == 0

    # Now test with the full set of new events. We expect the orchestration to complete.
    executor = worker._OrchestrationExecutor(registry, TEST_LOGGER)
    result = executor.execute(TEST_INSTANCE_ID, old_events, new_events)
    actions = result.actions

    complete_action = get_and_validate_single_complete_workflow_action(actions)
    assert complete_action.workflowStatus == pb.ORCHESTRATION_STATUS_COMPLETED
    assert complete_action.result.value == '[0, 1, 2, 3, 4, 5, 6, 7, 8, 9]'


def test_fan_in_with_single_failure():
    """Tests that a fan-in pattern works correctly when one of the tasks fails"""

    def print_int(_, val: int):
        return str(val)

    def orchestrator(ctx: task.OrchestrationContext, _):
        tasks = []
        for i in range(10):
            tasks.append(ctx.call_activity(print_int, input=i))
        results = yield task.when_all(tasks)
        return results

    registry = worker._Registry()
    orchestrator_name = registry.add_orchestrator(orchestrator)
    activity_name = registry.add_activity(print_int)

    old_events = [
        helpers.new_workflow_started_event(),
        helpers.new_execution_started_event(
            orchestrator_name, TEST_INSTANCE_ID, encoded_input=None
        ),
    ]
    for i in range(10):
        old_events.append(
            helpers.new_task_scheduled_event(i + 1, activity_name, encoded_input=str(i))
        )

    # 5 of the tasks complete successfully, 1 fails, and 4 are still running.
    # The expectation is that the orchestration will fail immediately.
    new_events = []
    for i in range(5):
        new_events.append(
            helpers.new_task_completed_event(i + 1, encoded_output=print_int(None, i))
        )
    ex = Exception('Kah-BOOOOM!!!')
    new_events.append(helpers.new_task_failed_event(6, ex))

    # Now test with the full set of new events. We expect the orchestration to complete.
    executor = worker._OrchestrationExecutor(registry, TEST_LOGGER)
    result = executor.execute(TEST_INSTANCE_ID, old_events, new_events)
    actions = result.actions

    complete_action = get_and_validate_single_complete_workflow_action(actions)
    assert complete_action.workflowStatus == pb.ORCHESTRATION_STATUS_FAILED
    assert (
        complete_action.failureDetails.errorType == 'TaskFailedError'
    )  # TODO: Is this the right error type?
    assert str(ex) in complete_action.failureDetails.errorMessage


def test_when_any():
    """Tests that a when_any pattern works correctly"""

    def hello(_, name: str):
        return f'Hello {name}!'

    def orchestrator(ctx: task.OrchestrationContext, _):
        t1 = ctx.call_activity(hello, input='Tokyo')
        t2 = ctx.call_activity(hello, input='Seattle')
        winner = yield task.when_any([t1, t2])
        if winner == t1:
            return t1.get_result()
        else:
            return t2.get_result()

    registry = worker._Registry()
    orchestrator_name = registry.add_orchestrator(orchestrator)
    activity_name = registry.add_activity(hello)

    # Test 1: Start the orchestration and let it yield on the when_any. We expect the orchestration
    # to return two actions: one to schedule the "Tokyo" task and one to schedule the "Seattle" task.
    old_events = []
    new_events = [
        helpers.new_execution_started_event(orchestrator_name, TEST_INSTANCE_ID, encoded_input=None)
    ]
    executor = worker._OrchestrationExecutor(registry, TEST_LOGGER)
    result = executor.execute(TEST_INSTANCE_ID, old_events, new_events)
    actions = result.actions
    assert len(actions) == 2
    assert actions[0].HasField('scheduleTask')
    assert actions[1].HasField('scheduleTask')

    # The next tests assume that the orchestration has already awaited at the task.when_any()
    old_events = [
        helpers.new_workflow_started_event(),
        helpers.new_execution_started_event(
            orchestrator_name, TEST_INSTANCE_ID, encoded_input=None
        ),
        helpers.new_task_scheduled_event(1, activity_name, encoded_input=json.dumps('Tokyo')),
        helpers.new_task_scheduled_event(2, activity_name, encoded_input=json.dumps('Seattle')),
    ]

    # Test 2: Complete the "Tokyo" task. We expect the orchestration to complete with output "Hello, Tokyo!"
    encoded_output = json.dumps(hello(None, 'Tokyo'))
    new_events = [helpers.new_task_completed_event(1, encoded_output)]
    executor = worker._OrchestrationExecutor(registry, TEST_LOGGER)
    result = executor.execute(TEST_INSTANCE_ID, old_events, new_events)
    actions = result.actions
    complete_action = get_and_validate_single_complete_workflow_action(actions)
    assert complete_action.workflowStatus == pb.ORCHESTRATION_STATUS_COMPLETED
    assert complete_action.result.value == encoded_output

    # Test 3: Complete the "Seattle" task. We expect the orchestration to complete with output "Hello, Seattle!"
    encoded_output = json.dumps(hello(None, 'Seattle'))
    new_events = [helpers.new_task_completed_event(2, encoded_output)]
    executor = worker._OrchestrationExecutor(registry, TEST_LOGGER)
    result = executor.execute(TEST_INSTANCE_ID, old_events, new_events)
    actions = result.actions
    complete_action = get_and_validate_single_complete_workflow_action(actions)
    assert complete_action.workflowStatus == pb.ORCHESTRATION_STATUS_COMPLETED
    assert complete_action.result.value == encoded_output


def test_when_any_with_retry():
    """Tests that a when_any pattern works correctly with retries"""

    def dummy_activity(_, inp: str):
        if inp == 'Tokyo':
            raise ValueError('Kah-BOOOOM!!!')
        return f'Hello {inp}!'

    def orchestrator(ctx: task.OrchestrationContext, _):
        t1 = ctx.call_activity(
            dummy_activity,
            retry_policy=task.RetryPolicy(
                first_retry_interval=timedelta(seconds=1),
                max_number_of_attempts=6,
                backoff_coefficient=2,
                max_retry_interval=timedelta(seconds=10),
                retry_timeout=timedelta(seconds=50),
            ),
            input='Tokyo',
        )
        t2 = ctx.call_activity(dummy_activity, input='Seattle')
        winner = yield task.when_any([t1, t2])
        if winner == t1:
            return t1.get_result()
        else:
            return t2.get_result()

    registry = worker._Registry()
    orchestrator_name = registry.add_orchestrator(orchestrator)
    registry.add_activity(dummy_activity)

    current_timestamp = datetime.utcnow()
    # Simulate the task failing for the first time and confirm that a timer is scheduled for 1 second in the future
    old_events = [
        helpers.new_workflow_started_event(timestamp=current_timestamp),
        helpers.new_execution_started_event(
            orchestrator_name, TEST_INSTANCE_ID, encoded_input=None
        ),
        helpers.new_task_scheduled_event(1, task.get_name(dummy_activity)),
        helpers.new_task_scheduled_event(2, task.get_name(dummy_activity)),
    ]
    expected_fire_at = current_timestamp + timedelta(seconds=1)

    new_events = [
        helpers.new_workflow_started_event(timestamp=current_timestamp),
        helpers.new_task_failed_event(1, ValueError('Kah-BOOOOM!!!')),
    ]
    executor = worker._OrchestrationExecutor(registry, TEST_LOGGER)
    result = executor.execute(TEST_INSTANCE_ID, old_events, new_events)
    actions = result.actions
    assert len(actions) == 1
    assert actions[0].HasField('createTimer')
    assert actions[0].createTimer.fireAt.ToDatetime() == expected_fire_at
    assert actions[0].id == 3

    # Simulate the timer firing at the expected time and confirm that another activity task is scheduled
    current_timestamp = expected_fire_at
    old_events = old_events + new_events
    new_events = [
        helpers.new_workflow_started_event(current_timestamp),
        helpers.new_timer_created_event(3, current_timestamp),
        helpers.new_timer_fired_event(3, current_timestamp),
    ]
    executor = worker._OrchestrationExecutor(registry, TEST_LOGGER)
    result = executor.execute(TEST_INSTANCE_ID, old_events, new_events)
    actions = result.actions
    assert len(actions) == 1
    assert actions[0].HasField('scheduleTask')
    assert actions[0].id == 4  # New sequence number for retry

    # Simulate the task failing for the second time and confirm that a timer is scheduled for 2 seconds in the future
    old_events = old_events + new_events
    expected_fire_at = current_timestamp + timedelta(seconds=2)
    new_events = [
        helpers.new_workflow_started_event(current_timestamp),
        helpers.new_task_scheduled_event(4, task.get_name(dummy_activity)),
        helpers.new_task_failed_event(4, ValueError('Kah-BOOOOM!!!')),
    ]
    executor = worker._OrchestrationExecutor(registry, TEST_LOGGER)
    result = executor.execute(TEST_INSTANCE_ID, old_events, new_events)
    actions = result.actions
    assert len(actions) == 1
    assert actions[0].HasField('createTimer')
    assert actions[0].createTimer.fireAt.ToDatetime() == expected_fire_at
    assert actions[0].id == 5

    # Complete the "Seattle" task. We expect the orchestration to complete with output "Hello, Seattle!"
    encoded_output = json.dumps(dummy_activity(None, 'Seattle'))
    new_events = [helpers.new_task_completed_event(2, encoded_output)]
    executor = worker._OrchestrationExecutor(registry, TEST_LOGGER)
    result = executor.execute(TEST_INSTANCE_ID, old_events, new_events)
    actions = result.actions
    complete_action = get_and_validate_single_complete_workflow_action(actions)
    assert complete_action.workflowStatus == pb.ORCHESTRATION_STATUS_COMPLETED
    assert complete_action.result.value == encoded_output


def test_when_all_with_retry():
    """Tests that a when_all pattern works correctly with retries"""

    def dummy_activity(ctx, inp: str):
        if inp == 'Tokyo':
            raise ValueError('Kah-BOOOOM!!!')
        return f'Hello {inp}!'

    def orchestrator(ctx: task.OrchestrationContext, _):
        t1 = ctx.call_activity(
            dummy_activity,
            retry_policy=task.RetryPolicy(
                first_retry_interval=timedelta(seconds=2),
                max_number_of_attempts=3,
                backoff_coefficient=4,
                max_retry_interval=timedelta(seconds=5),
                retry_timeout=timedelta(seconds=50),
            ),
            input='Tokyo',
        )
        t2 = ctx.call_activity(dummy_activity, input='Seattle')
        results = yield task.when_all([t1, t2])
        return results

    registry = worker._Registry()
    orchestrator_name = registry.add_orchestrator(orchestrator)
    registry.add_activity(dummy_activity)

    current_timestamp = datetime.utcnow()
    # Simulate the task failing for the first time and confirm that a timer is scheduled for 2 seconds in the future
    old_events = [
        helpers.new_workflow_started_event(timestamp=current_timestamp),
        helpers.new_execution_started_event(
            orchestrator_name, TEST_INSTANCE_ID, encoded_input=None
        ),
        helpers.new_task_scheduled_event(1, task.get_name(dummy_activity)),
        helpers.new_task_scheduled_event(2, task.get_name(dummy_activity)),
    ]
    expected_fire_at = current_timestamp + timedelta(seconds=2)

    new_events = [
        helpers.new_workflow_started_event(timestamp=current_timestamp),
        helpers.new_task_failed_event(1, ValueError('Kah-BOOOOM!!!')),
    ]
    executor = worker._OrchestrationExecutor(registry, TEST_LOGGER)
    result = executor.execute(TEST_INSTANCE_ID, old_events, new_events)
    actions = result.actions
    assert len(actions) == 1
    assert actions[0].HasField('createTimer')
    assert actions[0].createTimer.fireAt.ToDatetime() == expected_fire_at
    assert actions[0].id == 3

    # Simulate the timer firing at the expected time and confirm that another activity task is scheduled
    current_timestamp = expected_fire_at
    old_events = old_events + new_events
    new_events = [
        helpers.new_workflow_started_event(current_timestamp),
        helpers.new_timer_created_event(3, current_timestamp),
        helpers.new_timer_fired_event(3, current_timestamp),
    ]
    executor = worker._OrchestrationExecutor(registry, TEST_LOGGER)
    result = executor.execute(TEST_INSTANCE_ID, old_events, new_events)
    actions = result.actions
    assert len(actions) == 1
    assert actions[0].HasField('scheduleTask')
    assert actions[0].id == 4  # New sequence number for retry

    # Simulate the task failing for the second time and confirm that a timer is scheduled for 5 seconds in the future
    old_events = old_events + new_events
    expected_fire_at = current_timestamp + timedelta(seconds=5)
    new_events = [
        helpers.new_workflow_started_event(current_timestamp),
        helpers.new_task_scheduled_event(4, task.get_name(dummy_activity)),
        helpers.new_task_failed_event(4, ValueError('Kah-BOOOOM!!!')),
    ]
    executor = worker._OrchestrationExecutor(registry, TEST_LOGGER)
    result = executor.execute(TEST_INSTANCE_ID, old_events, new_events)
    actions = result.actions
    assert len(actions) == 1
    assert actions[0].HasField('createTimer')
    assert actions[0].createTimer.fireAt.ToDatetime() == expected_fire_at
    assert actions[0].id == 5

    # Complete the "Seattle" task.
    # And, Simulate the timer firing at the expected time and confirm that another activity task is scheduled
    encoded_output = json.dumps(dummy_activity(None, 'Seattle'))
    old_events = old_events + new_events
    new_events = [
        helpers.new_task_completed_event(2, encoded_output),
        helpers.new_timer_created_event(5, current_timestamp),
        helpers.new_timer_fired_event(5, current_timestamp),
    ]
    executor = worker._OrchestrationExecutor(registry, TEST_LOGGER)
    result = executor.execute(TEST_INSTANCE_ID, old_events, new_events)
    actions = result.actions
    assert len(actions) == 1
    assert actions[0].HasField('scheduleTask')
    assert actions[0].id == 6  # New sequence number for retry

    ex = ValueError('Kah-BOOOOM!!!')

    # Simulate the task failing for the third time. Overall workflow should fail at this point.
    old_events = old_events + new_events
    new_events = [
        helpers.new_workflow_started_event(current_timestamp),
        helpers.new_task_scheduled_event(6, task.get_name(dummy_activity)),
        helpers.new_task_failed_event(6, ValueError('Kah-BOOOOM!!!')),
    ]
    executor = worker._OrchestrationExecutor(registry, TEST_LOGGER)
    result = executor.execute(TEST_INSTANCE_ID, old_events, new_events)
    actions = result.actions
    complete_action = get_and_validate_single_complete_workflow_action(actions)
    assert complete_action.workflowStatus == pb.ORCHESTRATION_STATUS_FAILED
    assert (
        complete_action.failureDetails.errorType == 'TaskFailedError'
    )  # TODO: Should this be the specific error?
    assert str(ex) in complete_action.failureDetails.errorMessage


def test_activity_non_retryable_default_exception():
    """If activity fails with NonRetryableError, it should not be retried and orchestration should fail immediately."""

    def dummy_activity(ctx, _):
        raise task.NonRetryableError('boom')

    def orchestrator(ctx: task.OrchestrationContext, _):
        yield ctx.call_activity(
            dummy_activity,
            retry_policy=task.RetryPolicy(
                first_retry_interval=timedelta(seconds=1),
                max_number_of_attempts=3,
                backoff_coefficient=1,
            ),
        )

    registry = worker._Registry()
    name = registry.add_orchestrator(orchestrator)

    current_timestamp = datetime.utcnow()
    old_events = [
        helpers.new_workflow_started_event(timestamp=current_timestamp),
        helpers.new_execution_started_event(name, TEST_INSTANCE_ID, encoded_input=None),
        helpers.new_task_scheduled_event(1, task.get_name(dummy_activity)),
    ]
    new_events = [
        helpers.new_workflow_started_event(timestamp=current_timestamp),
        helpers.new_task_failed_event(1, task.NonRetryableError('boom')),
    ]

    executor = worker._OrchestrationExecutor(registry, TEST_LOGGER)
    result = executor.execute(TEST_INSTANCE_ID, old_events, new_events)
    actions = result.actions
    complete_action = get_and_validate_single_complete_workflow_action(actions)
    assert complete_action.workflowStatus == pb.ORCHESTRATION_STATUS_FAILED
    assert complete_action.failureDetails.errorMessage.__contains__('Activity task #1 failed: boom')


def test_activity_non_retryable_policy_name():
    """If policy marks ValueError as non-retryable (by name), fail immediately without retry."""

    def dummy_activity(ctx, _):
        raise ValueError('boom')

    def orchestrator(ctx: task.OrchestrationContext, _):
        yield ctx.call_activity(
            dummy_activity,
            retry_policy=task.RetryPolicy(
                first_retry_interval=timedelta(seconds=1),
                max_number_of_attempts=5,
                non_retryable_error_types=['ValueError'],
            ),
        )

    registry = worker._Registry()
    name = registry.add_orchestrator(orchestrator)

    current_timestamp = datetime.utcnow()
    old_events = [
        helpers.new_workflow_started_event(timestamp=current_timestamp),
        helpers.new_execution_started_event(name, TEST_INSTANCE_ID, encoded_input=None),
        helpers.new_task_scheduled_event(1, task.get_name(dummy_activity)),
    ]
    new_events = [
        helpers.new_workflow_started_event(timestamp=current_timestamp),
        helpers.new_task_failed_event(1, ValueError('boom')),
    ]

    executor = worker._OrchestrationExecutor(registry, TEST_LOGGER)
    result = executor.execute(TEST_INSTANCE_ID, old_events, new_events)
    actions = result.actions
    complete_action = get_and_validate_single_complete_workflow_action(actions)
    assert complete_action.workflowStatus == pb.ORCHESTRATION_STATUS_FAILED
    assert complete_action.failureDetails.errorMessage.__contains__('Activity task #1 failed: boom')


def test_activity_generic_exception_is_retryable():
    """Verify that generic Exception is retryable by default (not treated as non-retryable)."""

    def dummy_activity(ctx, _):
        raise Exception('generic error')

    def orchestrator(ctx: task.OrchestrationContext, _):
        yield ctx.call_activity(
            dummy_activity,
            retry_policy=task.RetryPolicy(
                first_retry_interval=timedelta(seconds=1),
                max_number_of_attempts=3,
                backoff_coefficient=1,
            ),
        )

    registry = worker._Registry()
    name = registry.add_orchestrator(orchestrator)

    current_timestamp = datetime.utcnow()
    # First attempt fails
    old_events = [
        helpers.new_workflow_started_event(timestamp=current_timestamp),
        helpers.new_execution_started_event(name, TEST_INSTANCE_ID, encoded_input=None),
        helpers.new_task_scheduled_event(1, task.get_name(dummy_activity)),
    ]
    new_events = [
        helpers.new_workflow_started_event(timestamp=current_timestamp),
        helpers.new_task_failed_event(1, Exception('generic error')),
    ]

    executor = worker._OrchestrationExecutor(registry, TEST_LOGGER)
    result = executor.execute(TEST_INSTANCE_ID, old_events, new_events)
    actions = result.actions
    # Should schedule a retry timer, not fail immediately
    assert len(actions) == 1
    assert actions[0].HasField('createTimer')
    assert actions[0].id == 2

    # Simulate the timer firing and activity being rescheduled
    expected_fire_at = current_timestamp + timedelta(seconds=1)
    old_events = old_events + new_events
    current_timestamp = expected_fire_at
    new_events = [
        helpers.new_workflow_started_event(current_timestamp),
        helpers.new_timer_created_event(2, current_timestamp),
        helpers.new_timer_fired_event(2, current_timestamp),
    ]
    executor = worker._OrchestrationExecutor(registry, TEST_LOGGER)
    result = executor.execute(TEST_INSTANCE_ID, old_events, new_events)
    actions = result.actions
    assert len(actions) == 1  # rescheduled task only (timer consumed)
    assert actions[0].HasField('scheduleTask')
    assert actions[0].id == 3  # New sequence number for retry

    # Second attempt also fails
    old_events = old_events + new_events
    new_events = [
        helpers.new_workflow_started_event(current_timestamp),
        helpers.new_task_scheduled_event(3, task.get_name(dummy_activity)),
        helpers.new_task_failed_event(3, Exception('generic error')),
    ]

    executor = worker._OrchestrationExecutor(registry, TEST_LOGGER)
    result = executor.execute(TEST_INSTANCE_ID, old_events, new_events)
    actions = result.actions
    # Should schedule another retry timer
    assert len(actions) == 1
    assert actions[0].HasField('createTimer')
    assert actions[0].id == 4

    # Simulate the timer firing and activity being rescheduled
    expected_fire_at = current_timestamp + timedelta(seconds=1)
    old_events = old_events + new_events
    current_timestamp = expected_fire_at
    new_events = [
        helpers.new_workflow_started_event(current_timestamp),
        helpers.new_timer_created_event(4, current_timestamp),
        helpers.new_timer_fired_event(4, current_timestamp),
    ]
    executor = worker._OrchestrationExecutor(registry, TEST_LOGGER)
    result = executor.execute(TEST_INSTANCE_ID, old_events, new_events)
    actions = result.actions
    assert len(actions) == 1  # rescheduled task only (timer consumed)
    assert actions[0].HasField('scheduleTask')
    assert actions[0].id == 5  # New sequence number for retry

    # Third attempt fails - should exhaust retries
    old_events = old_events + new_events
    new_events = [
        helpers.new_workflow_started_event(current_timestamp),
        helpers.new_task_scheduled_event(5, task.get_name(dummy_activity)),
        helpers.new_task_failed_event(5, Exception('generic error')),
    ]

    executor = worker._OrchestrationExecutor(registry, TEST_LOGGER)
    result = executor.execute(TEST_INSTANCE_ID, old_events, new_events)
    actions = result.actions
    # Now should fail - no more retries
    complete_action = get_and_validate_single_complete_workflow_action(actions)
    assert complete_action.workflowStatus == pb.ORCHESTRATION_STATUS_FAILED
    assert complete_action.failureDetails.errorMessage.__contains__(
        'Activity task #5 failed: generic error'
    )


def test_sub_orchestration_non_retryable_default_exception():
    """If sub-orchestrator fails with NonRetryableError, do not retry and fail immediately."""

    def child(ctx: task.OrchestrationContext, _):
        pass

    def parent(ctx: task.OrchestrationContext, _):
        yield ctx.call_sub_orchestrator(
            child,
            retry_policy=task.RetryPolicy(
                first_retry_interval=timedelta(seconds=1),
                max_number_of_attempts=3,
            ),
        )

    registry = worker._Registry()
    child_name = registry.add_orchestrator(child)
    parent_name = registry.add_orchestrator(parent)

    current_timestamp = datetime.utcnow()
    old_events = [
        helpers.new_workflow_started_event(timestamp=current_timestamp),
        helpers.new_execution_started_event(parent_name, TEST_INSTANCE_ID, encoded_input=None),
        helpers.new_child_workflow_created_event(1, child_name, 'sub-1', encoded_input=None),
    ]
    new_events = [
        helpers.new_workflow_started_event(timestamp=current_timestamp),
        helpers.new_child_workflow_failed_event(1, task.NonRetryableError('boom')),
    ]

    executor = worker._OrchestrationExecutor(registry, TEST_LOGGER)
    result = executor.execute(TEST_INSTANCE_ID, old_events, new_events)
    actions = result.actions
    complete_action = get_and_validate_single_complete_workflow_action(actions)
    assert complete_action.workflowStatus == pb.ORCHESTRATION_STATUS_FAILED
    assert complete_action.failureDetails.errorMessage.__contains__(
        'Sub-orchestration task #1 failed: boom'
    )


def test_sub_orchestration_non_retryable_policy_type():
    """If policy marks ValueError as non-retryable (by class), fail immediately without retry."""

    def child(ctx: task.OrchestrationContext, _):
        pass

    def parent(ctx: task.OrchestrationContext, _):
        yield ctx.call_sub_orchestrator(
            child,
            retry_policy=task.RetryPolicy(
                first_retry_interval=timedelta(seconds=1),
                max_number_of_attempts=5,
                non_retryable_error_types=[ValueError],
            ),
        )

    registry = worker._Registry()
    child_name = registry.add_orchestrator(child)
    parent_name = registry.add_orchestrator(parent)

    current_timestamp = datetime.utcnow()
    old_events = [
        helpers.new_workflow_started_event(timestamp=current_timestamp),
        helpers.new_execution_started_event(parent_name, TEST_INSTANCE_ID, encoded_input=None),
        helpers.new_child_workflow_created_event(1, child_name, 'sub-1', encoded_input=None),
    ]
    new_events = [
        helpers.new_workflow_started_event(timestamp=current_timestamp),
        helpers.new_child_workflow_failed_event(1, ValueError('boom')),
    ]

    executor = worker._OrchestrationExecutor(registry, TEST_LOGGER)
    result = executor.execute(TEST_INSTANCE_ID, old_events, new_events)
    actions = result.actions
    complete_action = get_and_validate_single_complete_workflow_action(actions)
    assert complete_action.workflowStatus == pb.ORCHESTRATION_STATUS_FAILED
    assert complete_action.failureDetails.errorMessage.__contains__(
        'Sub-orchestration task #1 failed: boom'
    )


def test_create_timer_sets_create_timer_origin():
    """Tests that create_timer sets TimerOriginCreateTimer on the CreateTimerAction."""

    def delay_orchestrator(ctx: task.OrchestrationContext, _):
        due_time = ctx.current_utc_datetime + timedelta(seconds=5)
        yield ctx.create_timer(due_time)
        return 'done'

    registry = worker._Registry()
    name = registry.add_orchestrator(delay_orchestrator)

    start_time = datetime(2020, 1, 1, 12, 0, 0)
    new_events = [
        helpers.new_workflow_started_event(start_time),
        helpers.new_execution_started_event(name, TEST_INSTANCE_ID, encoded_input=None),
    ]
    executor = worker._OrchestrationExecutor(registry, TEST_LOGGER)
    result = executor.execute(TEST_INSTANCE_ID, [], new_events)
    actions = result.actions

    assert len(actions) == 1
    assert actions[0].HasField('createTimer')
    timer_action = actions[0].createTimer
    assert timer_action.WhichOneof('origin') == 'createTimer'


def test_wait_for_external_event_timeout_sets_external_event_origin():
    """Tests that wait_for_external_event with timeout creates a timer with
    TimerOriginExternalEvent origin containing the event name."""

    def timeout_orchestrator(ctx: task.OrchestrationContext, _):
        result = yield ctx.wait_for_external_event('myEvent', timeout=timedelta(seconds=30))
        return result

    registry = worker._Registry()
    name = registry.add_orchestrator(timeout_orchestrator)

    start_time = datetime(2020, 1, 1, 12, 0, 0)
    new_events = [
        helpers.new_workflow_started_event(start_time),
        helpers.new_execution_started_event(name, TEST_INSTANCE_ID, encoded_input=None),
    ]
    executor = worker._OrchestrationExecutor(registry, TEST_LOGGER)
    result = executor.execute(TEST_INSTANCE_ID, [], new_events)
    actions = result.actions

    # The only action should be the timer (the external event wait doesn't produce an action)
    assert len(actions) == 1
    assert actions[0].HasField('createTimer')
    timer_action = actions[0].createTimer
    assert timer_action.WhichOneof('origin') == 'externalEvent'
    assert timer_action.externalEvent.name == 'myEvent'


def test_wait_for_external_event_timeout_fires_raises_timeout_error():
    """Tests that when the timeout fires before the event arrives, the task
    raises a TimeoutError."""

    def timeout_orchestrator(ctx: task.OrchestrationContext, _):
        try:
            result = yield ctx.wait_for_external_event('myEvent', timeout=timedelta(seconds=5))
            return f'got: {result}'
        except TimeoutError:
            return 'timed out'

    registry = worker._Registry()
    name = registry.add_orchestrator(timeout_orchestrator)

    start_time = datetime(2020, 1, 1, 12, 0, 0)
    fire_at = start_time + timedelta(seconds=5)

    # First execution: creates the timer
    old_events = [
        helpers.new_workflow_started_event(start_time),
        helpers.new_execution_started_event(name, TEST_INSTANCE_ID, encoded_input=None),
        helpers.new_timer_created_event(1, fire_at),
    ]
    # Timer fires before event arrives
    new_events = [
        helpers.new_timer_fired_event(1, fire_at),
    ]
    executor = worker._OrchestrationExecutor(registry, TEST_LOGGER)
    result = executor.execute(TEST_INSTANCE_ID, old_events, new_events)
    actions = result.actions

    complete_action = get_and_validate_single_complete_workflow_action(actions)
    assert complete_action.workflowStatus == pb.ORCHESTRATION_STATUS_COMPLETED
    assert complete_action.result.value == json.dumps('timed out')


def test_wait_for_external_event_with_timeout_event_arrives_first():
    """Tests that when the event arrives before the timeout, the task completes
    with the event data."""

    def timeout_orchestrator(ctx: task.OrchestrationContext, _):
        try:
            result = yield ctx.wait_for_external_event('myEvent', timeout=timedelta(seconds=30))
            return f'got: {result}'
        except TimeoutError:
            return 'timed out'

    registry = worker._Registry()
    name = registry.add_orchestrator(timeout_orchestrator)

    start_time = datetime(2020, 1, 1, 12, 0, 0)

    # First execution: creates the timer (id=1)
    old_events = [
        helpers.new_workflow_started_event(start_time),
        helpers.new_execution_started_event(name, TEST_INSTANCE_ID, encoded_input=None),
        helpers.new_timer_created_event(1, start_time + timedelta(seconds=30)),
    ]
    # Event arrives before the timer fires
    new_events = [
        helpers.new_event_raised_event('myEvent', json.dumps('hello')),
    ]
    executor = worker._OrchestrationExecutor(registry, TEST_LOGGER)
    result = executor.execute(TEST_INSTANCE_ID, old_events, new_events)
    actions = result.actions

    complete_action = get_and_validate_single_complete_workflow_action(actions)
    assert complete_action.workflowStatus == pb.ORCHESTRATION_STATUS_COMPLETED
    assert complete_action.result.value == json.dumps('got: hello')


def test_wait_for_external_event_timeout_cleans_up_pending_event():
    """When the timeout timer fires first, the stale event task is unregistered
    from _pending_events so that a subsequent wait_for_external_event for the
    same name can observe a later event rather than having it consumed by the
    timed-out waiter."""

    def orchestrator(ctx: task.OrchestrationContext, _):
        try:
            yield ctx.wait_for_external_event('myEvent', timeout=timedelta(seconds=5))
        except TimeoutError:
            pass
        # Second wait for the same event name — must pick up the late event.
        result = yield ctx.wait_for_external_event('myEvent', timeout=timedelta(seconds=60))
        return result

    registry = worker._Registry()
    name = registry.add_orchestrator(orchestrator)

    start_time = datetime(2020, 1, 1, 12, 0, 0)
    fire_at = start_time + timedelta(seconds=5)

    # First wait creates timer at id=1, fires. Second wait creates timer at id=2.
    old_events = [
        helpers.new_workflow_started_event(start_time),
        helpers.new_execution_started_event(name, TEST_INSTANCE_ID, encoded_input=None),
        helpers.new_timer_created_event(1, fire_at),
        helpers.new_timer_fired_event(1, fire_at),
        helpers.new_timer_created_event(2, start_time + timedelta(seconds=60)),
    ]
    # The late event arrives during the second wait.
    new_events = [
        helpers.new_event_raised_event('myEvent', json.dumps('late hello')),
    ]
    executor = worker._OrchestrationExecutor(registry, TEST_LOGGER)
    result = executor.execute(TEST_INSTANCE_ID, old_events, new_events)
    actions = result.actions

    complete_action = get_and_validate_single_complete_workflow_action(actions)
    assert complete_action.workflowStatus == pb.ORCHESTRATION_STATUS_COMPLETED
    assert complete_action.result.value == json.dumps('late hello')


def test_wait_for_external_event_indefinite_emits_optional_timer():
    """WaitForExternalEvent with no timeout (or a negative timeout) emits an
    optional timer whose fireAt is the exact sentinel 9999-12-31T23:59:59.999999999Z."""

    def orchestrator(ctx: task.OrchestrationContext, _):
        result = yield ctx.wait_for_external_event('myEvent')
        return result

    registry = worker._Registry()
    name = registry.add_orchestrator(orchestrator)

    start_time = datetime(2020, 1, 1, 12, 0, 0)
    new_events = [
        helpers.new_workflow_started_event(start_time),
        helpers.new_execution_started_event(name, TEST_INSTANCE_ID, encoded_input=None),
    ]
    executor = worker._OrchestrationExecutor(registry, TEST_LOGGER)
    result = executor.execute(TEST_INSTANCE_ID, [], new_events)
    actions = result.actions

    assert len(actions) == 1
    assert actions[0].HasField('createTimer')
    timer_action = actions[0].createTimer
    assert timer_action.WhichOneof('origin') == 'externalEvent'
    assert timer_action.externalEvent.name == 'myEvent'
    # Exact sentinel match — bit-for-bit, including nanoseconds.
    assert timer_action.fireAt.seconds == helpers.OPTIONAL_TIMER_FIRE_AT.seconds
    assert timer_action.fireAt.nanos == helpers.OPTIONAL_TIMER_FIRE_AT.nanos
    assert helpers.is_optional_timer_action(actions[0])


def test_wait_for_external_event_zero_timeout_emits_no_timer():
    """WaitForExternalEvent with timeout=0 emits no timer and the returned task is
    immediately canceled (fails with TimeoutError)."""

    def orchestrator(ctx: task.OrchestrationContext, _):
        try:
            result = yield ctx.wait_for_external_event('myEvent', timeout=timedelta(0))
            return f'got: {result}'
        except TimeoutError:
            return 'canceled'

    registry = worker._Registry()
    name = registry.add_orchestrator(orchestrator)

    start_time = datetime(2020, 1, 1, 12, 0, 0)
    new_events = [
        helpers.new_workflow_started_event(start_time),
        helpers.new_execution_started_event(name, TEST_INSTANCE_ID, encoded_input=None),
    ]
    executor = worker._OrchestrationExecutor(registry, TEST_LOGGER)
    result = executor.execute(TEST_INSTANCE_ID, [], new_events)
    actions = result.actions

    # Only the completion action is emitted — no CreateTimerAction.
    complete_action = get_and_validate_single_complete_workflow_action(actions)
    assert complete_action.workflowStatus == pb.ORCHESTRATION_STATUS_COMPLETED
    assert complete_action.result.value == json.dumps('canceled')


def test_post_patch_replay_optional_timer_matches_history():
    """A post-patch history containing the optional TimerCreated event replays
    through the normal match path without shifting."""

    def orchestrator(ctx: task.OrchestrationContext, _):
        result = yield ctx.wait_for_external_event('myEvent')
        return result

    registry = worker._Registry()
    name = registry.add_orchestrator(orchestrator)

    start_time = datetime(2020, 1, 1, 12, 0, 0)
    old_events = [
        helpers.new_workflow_started_event(start_time),
        helpers.new_execution_started_event(name, TEST_INSTANCE_ID, encoded_input=None),
        helpers.new_timer_created_event(
            1,
            helpers.OPTIONAL_TIMER_FIRE_AT,
            origin=pb.TimerOriginExternalEvent(name='myEvent'),
        ),
    ]
    new_events = [helpers.new_event_raised_event('myEvent', encoded_input=json.dumps('ok'))]
    executor = worker._OrchestrationExecutor(registry, TEST_LOGGER)
    result = executor.execute(TEST_INSTANCE_ID, old_events, new_events)
    actions = result.actions

    complete_action = get_and_validate_single_complete_workflow_action(actions)
    assert complete_action.workflowStatus == pb.ORCHESTRATION_STATUS_COMPLETED
    assert complete_action.result.value == json.dumps('ok')


def test_post_patch_replay_optional_timer_with_unset_origin():
    """An older sidecar may emit TimerCreatedEvent without populating the proto3
    ``origin`` oneof. The sentinel fireAt alone must still classify the event as
    optional so the replay matches our pending optional timer cleanly."""

    def orchestrator(ctx: task.OrchestrationContext, _):
        result = yield ctx.wait_for_external_event('myEvent')
        return result

    registry = worker._Registry()
    name = registry.add_orchestrator(orchestrator)

    start_time = datetime(2020, 1, 1, 12, 0, 0)
    old_events = [
        helpers.new_workflow_started_event(start_time),
        helpers.new_execution_started_event(name, TEST_INSTANCE_ID, encoded_input=None),
        # Sentinel fireAt but no origin set.
        helpers.new_timer_created_event(1, helpers.OPTIONAL_TIMER_FIRE_AT),
    ]
    new_events = [helpers.new_event_raised_event('myEvent', encoded_input=json.dumps('ok'))]
    executor = worker._OrchestrationExecutor(registry, TEST_LOGGER)
    result = executor.execute(TEST_INSTANCE_ID, old_events, new_events)
    actions = result.actions

    complete_action = get_and_validate_single_complete_workflow_action(actions)
    assert complete_action.workflowStatus == pb.ORCHESTRATION_STATUS_COMPLETED
    assert complete_action.result.value == json.dumps('ok')


def test_patch_adds_activity_before_existing_wait():
    """Reproduces the versioning.py test5/test6 scenario.

    An in-flight orchestration had a wait_for_external_event that emitted an
    optional TimerCreated event into history. Later, the code was patched to add
    an ``is_patched`` check + activity call *before* the wait. On replay, the
    new orchestration code emits a ScheduleTask at the id that the optional
    TimerCreated occupies in history. The runtime must silently skip the stale
    optional TimerCreated event rather than raising a non-determinism error."""

    def dummy_activity(ctx, input):
        return f'did: {input}'

    def patched_orchestrator(ctx: task.OrchestrationContext, _):
        yield ctx.call_activity(dummy_activity, input='start')
        # NEW: is_patched branch added before the existing wait. Schedules an
        # activity at the id previously occupied by the optional timer.
        if ctx.is_patched('patch1'):
            yield ctx.call_activity(dummy_activity, input='patch1 is patched')
        else:
            yield ctx.call_activity(dummy_activity, input='patch1 is not patched')
        result = yield ctx.wait_for_external_event('evt')
        return result

    registry = worker._Registry()
    name = registry.add_orchestrator(patched_orchestrator)
    registry.add_activity(dummy_activity)

    start_time = datetime(2020, 1, 1, 12, 0, 0)
    # Pre-patch history: start activity at id=1, optional timer at id=2.
    old_events = [
        helpers.new_workflow_started_event(start_time),
        helpers.new_execution_started_event(name, TEST_INSTANCE_ID, encoded_input=None),
        helpers.new_task_scheduled_event(1, task.get_name(dummy_activity)),
        helpers.new_task_completed_event(1, json.dumps('did: start')),
        helpers.new_timer_created_event(
            2,
            helpers.OPTIONAL_TIMER_FIRE_AT,
            origin=pb.TimerOriginExternalEvent(name='evt'),
        ),
    ]
    # Event arrives (triggers replay with the new code path).
    new_events = [helpers.new_event_raised_event('evt', encoded_input=json.dumps('ok'))]
    executor = worker._OrchestrationExecutor(registry, TEST_LOGGER)
    result = executor.execute(TEST_INSTANCE_ID, old_events, new_events)
    actions = result.actions

    # Replay must NOT fail. It must emit the new patch1-not-patched activity as
    # a pending action (id=2 — the slot the stale optional timer is skipped from).
    # is_patched returns False during replay because the patch is not recorded in
    # the original history's workflowStarted patches.
    assert len(actions) == 1
    assert actions[0].HasField('scheduleTask')
    assert actions[0].scheduleTask.input.value == json.dumps('patch1 is not patched')


def test_pre_patch_replay_indefinite_wait_then_activity():
    """A pre-patch history has the activity scheduled at id=1 (no reserved id for
    the indefinite wait). The replay must drop the optional timer, shift the
    activity down to id=1, and complete cleanly."""

    def dummy_activity(ctx, _):
        return 'activity result'

    def orchestrator(ctx: task.OrchestrationContext, _):
        yield ctx.wait_for_external_event('myEvent')
        result = yield ctx.call_activity(dummy_activity)
        return result

    registry = worker._Registry()
    name = registry.add_orchestrator(orchestrator)
    registry.add_activity(dummy_activity)

    # Pre-patch history: no timerCreated for the wait, activity scheduled at id=1
    # (which would have been id=2 under post-patch numbering).
    start_time = datetime(2020, 1, 1, 12, 0, 0)
    old_events = [
        helpers.new_workflow_started_event(start_time),
        helpers.new_execution_started_event(name, TEST_INSTANCE_ID, encoded_input=None),
        helpers.new_event_raised_event('myEvent', encoded_input=json.dumps('go')),
        helpers.new_task_scheduled_event(1, task.get_name(dummy_activity)),
    ]
    new_events = [helpers.new_task_completed_event(1, json.dumps('activity result'))]
    executor = worker._OrchestrationExecutor(registry, TEST_LOGGER)
    result = executor.execute(TEST_INSTANCE_ID, old_events, new_events)
    actions = result.actions

    # A single completion action — no phantom createTimer leaks.
    complete_action = get_and_validate_single_complete_workflow_action(actions)
    assert complete_action.workflowStatus == pb.ORCHESTRATION_STATUS_COMPLETED
    assert complete_action.result.value == json.dumps('activity result')


def test_pre_patch_replay_indefinite_wait_then_child_workflow():
    """A pre-patch history with a child workflow scheduled after an indefinite
    wait — the shift logic must work for childWorkflowInstanceCreated too."""

    def child_orchestrator(ctx: task.OrchestrationContext, _):
        return 'child result'

    def parent_orchestrator(ctx: task.OrchestrationContext, _):
        yield ctx.wait_for_external_event('myEvent')
        result = yield ctx.call_sub_orchestrator('child_orchestrator')
        return result

    registry = worker._Registry()
    name = registry.add_orchestrator(parent_orchestrator)
    registry.add_orchestrator(child_orchestrator)

    start_time = datetime(2020, 1, 1, 12, 0, 0)
    # Pre-patch history: child workflow scheduled at id=1 (no reserved id for wait).
    child_instance_id = f'{TEST_INSTANCE_ID}:0001'
    old_events = [
        helpers.new_workflow_started_event(start_time),
        helpers.new_execution_started_event(name, TEST_INSTANCE_ID, encoded_input=None),
        helpers.new_event_raised_event('myEvent', encoded_input=json.dumps('go')),
        helpers.new_child_workflow_created_event(1, 'child_orchestrator', child_instance_id),
    ]
    new_events = [helpers.new_child_workflow_completed_event(1, json.dumps('child result'))]
    executor = worker._OrchestrationExecutor(registry, TEST_LOGGER)
    result = executor.execute(TEST_INSTANCE_ID, old_events, new_events)
    actions = result.actions

    complete_action = get_and_validate_single_complete_workflow_action(actions)
    assert complete_action.workflowStatus == pb.ORCHESTRATION_STATUS_COMPLETED
    assert complete_action.result.value == json.dumps('child result')


def test_pre_patch_replay_indefinite_wait_then_user_create_timer():
    """A pre-patch history has a user CreateTimer right after an indefinite wait.
    Both the pending action and the incoming event are CreateTimer — the SDK must
    distinguish optional (externalEvent + sentinel) from non-optional and shift."""

    def orchestrator(ctx: task.OrchestrationContext, _):
        yield ctx.wait_for_external_event('myEvent')
        yield ctx.create_timer(timedelta(seconds=5))
        return 'done'

    registry = worker._Registry()
    name = registry.add_orchestrator(orchestrator)

    start_time = datetime(2020, 1, 1, 12, 0, 0)
    # Pre-patch history: a non-optional (user) TimerCreated at id=1. The
    # post-patch code would have emitted the optional timer at id=1 and the user
    # timer at id=2; the shift must drop the optional and match the user timer.
    user_fire_at = start_time + timedelta(seconds=5)
    old_events = [
        helpers.new_workflow_started_event(start_time),
        helpers.new_execution_started_event(name, TEST_INSTANCE_ID, encoded_input=None),
        helpers.new_event_raised_event('myEvent', encoded_input=json.dumps('go')),
        helpers.new_timer_created_event(
            1,
            user_fire_at,
            origin=pb.TimerOriginCreateTimer(),
        ),
    ]
    new_events = [helpers.new_timer_fired_event(1, user_fire_at)]
    executor = worker._OrchestrationExecutor(registry, TEST_LOGGER)
    result = executor.execute(TEST_INSTANCE_ID, old_events, new_events)
    actions = result.actions

    complete_action = get_and_validate_single_complete_workflow_action(actions)
    assert complete_action.workflowStatus == pb.ORCHESTRATION_STATUS_COMPLETED
    assert complete_action.result.value == json.dumps('done')


def test_stale_optional_timer_event_does_not_match_user_timer():
    """A stale optional TimerCreated event in history must not be treated as
    confirmation of a non-optional user CreateTimer that now occupies the same id.

    Scenario: older code had an indefinite wait_for_external_event (optional timer
    at id=1). A patch replaced the wait with a user CreateTimer at the same id.
    The stale optional TimerCreated must be dropped; the user timer must remain
    pending and match its own (non-optional) TimerCreated on a future replay."""

    def patched_orchestrator(ctx: task.OrchestrationContext, _):
        # New code: user timer at id=1 (replaces the old indefinite wait).
        yield ctx.create_timer(timedelta(seconds=10))
        return 'done'

    registry = worker._Registry()
    name = registry.add_orchestrator(patched_orchestrator)

    start_time = datetime(2020, 1, 1, 12, 0, 0)
    user_fire_at = start_time + timedelta(seconds=10)
    # History from the old code: optional timer at id=1 (stale).
    old_events = [
        helpers.new_workflow_started_event(start_time),
        helpers.new_execution_started_event(name, TEST_INSTANCE_ID, encoded_input=None),
        helpers.new_timer_created_event(
            1,
            helpers.OPTIONAL_TIMER_FIRE_AT,
            origin=pb.TimerOriginExternalEvent(name='evt'),
        ),
    ]
    # New events: the runtime confirms and fires the real user timer at id=1.
    new_events = [
        helpers.new_timer_created_event(
            1,
            user_fire_at,
            origin=pb.TimerOriginCreateTimer(),
        ),
        helpers.new_timer_fired_event(1, user_fire_at),
    ]
    executor = worker._OrchestrationExecutor(registry, TEST_LOGGER)
    result = executor.execute(TEST_INSTANCE_ID, old_events, new_events)
    actions = result.actions

    # The stale optional event must have been dropped. The real user timer must
    # have been confirmed and fired, completing the orchestration.
    complete_action = get_and_validate_single_complete_workflow_action(actions)
    assert complete_action.workflowStatus == pb.ORCHESTRATION_STATUS_COMPLETED
    assert complete_action.result.value == json.dumps('done')


def test_pre_patch_replay_two_indefinite_waits():
    """Two indefinite waits in sequence. Shifts must compose across multiple
    optional timers."""

    def dummy_activity(ctx, _):
        return 'act result'

    def orchestrator(ctx: task.OrchestrationContext, _):
        yield ctx.wait_for_external_event('A')
        yield ctx.call_activity(dummy_activity)
        yield ctx.wait_for_external_event('B')
        result = yield ctx.call_activity(dummy_activity)
        return result

    registry = worker._Registry()
    name = registry.add_orchestrator(orchestrator)
    registry.add_activity(dummy_activity)

    start_time = datetime(2020, 1, 1, 12, 0, 0)
    # Pre-patch numbering: first activity id=1, second activity id=2 (both waits
    # consumed no sequence numbers).
    activity_name = task.get_name(dummy_activity)
    old_events = [
        helpers.new_workflow_started_event(start_time),
        helpers.new_execution_started_event(name, TEST_INSTANCE_ID, encoded_input=None),
        helpers.new_event_raised_event('A', encoded_input=json.dumps('a')),
        helpers.new_task_scheduled_event(1, activity_name),
        helpers.new_task_completed_event(1, json.dumps('act result')),
        helpers.new_event_raised_event('B', encoded_input=json.dumps('b')),
        helpers.new_task_scheduled_event(2, activity_name),
    ]
    new_events = [helpers.new_task_completed_event(2, json.dumps('act result'))]
    executor = worker._OrchestrationExecutor(registry, TEST_LOGGER)
    result = executor.execute(TEST_INSTANCE_ID, old_events, new_events)
    actions = result.actions

    complete_action = get_and_validate_single_complete_workflow_action(actions)
    assert complete_action.workflowStatus == pb.ORCHESTRATION_STATUS_COMPLETED
    assert complete_action.result.value == json.dumps('act result')


def test_activity_retry_timer_sets_activity_retry_origin():
    """Tests that retry timers for failed activities set TimerOriginActivityRetry
    with the correct taskExecutionId."""

    def dummy_activity(ctx, _):
        raise ValueError('boom')

    def orchestrator(ctx: task.OrchestrationContext, _):
        result = yield ctx.call_activity(
            dummy_activity,
            retry_policy=task.RetryPolicy(
                first_retry_interval=timedelta(seconds=1),
                max_number_of_attempts=3,
            ),
        )
        return result

    registry = worker._Registry()
    name = registry.add_orchestrator(orchestrator)

    current_timestamp = datetime(2020, 1, 1, 12, 0, 0)

    # Attempt 1: scheduleTask(id=1) fails
    old_events = [
        helpers.new_workflow_started_event(timestamp=current_timestamp),
        helpers.new_execution_started_event(name, TEST_INSTANCE_ID, encoded_input=None),
        helpers.new_task_scheduled_event(1, task.get_name(dummy_activity)),
    ]
    new_events = [
        helpers.new_workflow_started_event(timestamp=current_timestamp),
        helpers.new_task_failed_event(1, ValueError('boom')),
    ]
    executor = worker._OrchestrationExecutor(registry, TEST_LOGGER)
    result = executor.execute(TEST_INSTANCE_ID, old_events, new_events)
    actions = result.actions

    # The retry timer should have activityRetry origin
    assert len(actions) == 1
    assert actions[0].HasField('createTimer')
    timer_action = actions[0].createTimer
    assert timer_action.WhichOneof('origin') == 'activityRetry'
    assert timer_action.activityRetry.taskExecutionId != ''


def test_activity_retry_task_execution_id_stable_across_retries():
    """Tests that the taskExecutionId in TimerOriginActivityRetry is stable
    across multiple retry attempts of the same logical activity call."""

    def dummy_activity(ctx, _):
        raise ValueError('boom')

    def orchestrator(ctx: task.OrchestrationContext, _):
        result = yield ctx.call_activity(
            dummy_activity,
            retry_policy=task.RetryPolicy(
                first_retry_interval=timedelta(seconds=1),
                max_number_of_attempts=4,
            ),
        )
        return result

    registry = worker._Registry()
    name = registry.add_orchestrator(orchestrator)

    current_timestamp = datetime(2020, 1, 1, 12, 0, 0)

    # Attempt 1: scheduleTask(id=1) fails -> retry timer(id=2)
    old_events = [
        helpers.new_workflow_started_event(timestamp=current_timestamp),
        helpers.new_execution_started_event(name, TEST_INSTANCE_ID, encoded_input=None),
        helpers.new_task_scheduled_event(1, task.get_name(dummy_activity)),
    ]
    new_events = [
        helpers.new_workflow_started_event(timestamp=current_timestamp),
        helpers.new_task_failed_event(1, ValueError('boom')),
    ]
    executor = worker._OrchestrationExecutor(registry, TEST_LOGGER)
    result = executor.execute(TEST_INSTANCE_ID, old_events, new_events)
    actions = result.actions
    assert len(actions) == 1
    assert actions[0].HasField('createTimer')
    retry_timer_1 = actions[0].createTimer
    first_task_execution_id = retry_timer_1.activityRetry.taskExecutionId
    assert first_task_execution_id != ''

    # Timer fires -> scheduleTask(id=3), then fails -> retry timer(id=4)
    old_events = old_events + new_events
    current_timestamp = current_timestamp + timedelta(seconds=1)
    new_events = [
        helpers.new_workflow_started_event(current_timestamp),
        helpers.new_timer_created_event(2, current_timestamp),
        helpers.new_timer_fired_event(2, current_timestamp),
    ]
    executor = worker._OrchestrationExecutor(registry, TEST_LOGGER)
    result = executor.execute(TEST_INSTANCE_ID, old_events, new_events)
    actions = result.actions
    assert len(actions) == 1
    assert actions[0].HasField('scheduleTask')

    # Attempt 2 fails
    old_events = old_events + new_events
    new_events = [
        helpers.new_workflow_started_event(current_timestamp),
        helpers.new_task_scheduled_event(3, task.get_name(dummy_activity)),
        helpers.new_task_failed_event(3, ValueError('boom')),
    ]
    executor = worker._OrchestrationExecutor(registry, TEST_LOGGER)
    result = executor.execute(TEST_INSTANCE_ID, old_events, new_events)
    actions = result.actions
    assert len(actions) == 1
    assert actions[0].HasField('createTimer')
    retry_timer_2 = actions[0].createTimer
    second_task_execution_id = retry_timer_2.activityRetry.taskExecutionId

    # Both retry timers must carry the SAME taskExecutionId
    assert second_task_execution_id == first_task_execution_id


def test_child_workflow_retry_timer_sets_child_workflow_retry_origin():
    """Tests that retry timers for failed child workflows set
    TimerOriginChildWorkflowRetry with the correct instanceId."""

    def child_orchestrator(ctx: task.OrchestrationContext, _):
        raise ValueError('child failed')

    def parent_orchestrator(ctx: task.OrchestrationContext, _):
        result = yield ctx.call_sub_orchestrator(
            'child_orchestrator',
            retry_policy=task.RetryPolicy(
                first_retry_interval=timedelta(seconds=1),
                max_number_of_attempts=3,
            ),
        )
        return result

    registry = worker._Registry()
    name = registry.add_orchestrator(parent_orchestrator)
    registry.add_orchestrator(child_orchestrator)

    current_timestamp = datetime(2020, 1, 1, 12, 0, 0)

    # First child created with id=1 -> instance_id = "abc123:0001"
    expected_first_child_id = f'{TEST_INSTANCE_ID}:0001'
    old_events = [
        helpers.new_workflow_started_event(timestamp=current_timestamp),
        helpers.new_execution_started_event(name, TEST_INSTANCE_ID, encoded_input=None),
        helpers.new_child_workflow_created_event(1, 'child_orchestrator', expected_first_child_id),
    ]
    new_events = [
        helpers.new_workflow_started_event(timestamp=current_timestamp),
        helpers.new_child_workflow_failed_event(1, ValueError('child failed')),
    ]
    executor = worker._OrchestrationExecutor(registry, TEST_LOGGER)
    result = executor.execute(TEST_INSTANCE_ID, old_events, new_events)
    actions = result.actions

    assert len(actions) == 1
    assert actions[0].HasField('createTimer')
    timer_action = actions[0].createTimer
    assert timer_action.WhichOneof('origin') == 'childWorkflowRetry'
    assert timer_action.childWorkflowRetry.instanceId == expected_first_child_id


def test_child_workflow_retry_instance_id_always_points_to_first_child():
    """Tests that the instanceId in TimerOriginChildWorkflowRetry always
    references the first child workflow's instance ID, even across multiple retries."""

    def child_orchestrator(ctx: task.OrchestrationContext, _):
        raise ValueError('child failed')

    def parent_orchestrator(ctx: task.OrchestrationContext, _):
        result = yield ctx.call_sub_orchestrator(
            'child_orchestrator',
            retry_policy=task.RetryPolicy(
                first_retry_interval=timedelta(seconds=1),
                max_number_of_attempts=4,
            ),
        )
        return result

    registry = worker._Registry()
    name = registry.add_orchestrator(parent_orchestrator)
    registry.add_orchestrator(child_orchestrator)

    current_timestamp = datetime(2020, 1, 1, 12, 0, 0)

    # First child: sub-orch(id=1) -> instance_id = "abc123:0001"
    expected_first_child_id = f'{TEST_INSTANCE_ID}:0001'
    old_events = [
        helpers.new_workflow_started_event(timestamp=current_timestamp),
        helpers.new_execution_started_event(name, TEST_INSTANCE_ID, encoded_input=None),
        helpers.new_child_workflow_created_event(1, 'child_orchestrator', expected_first_child_id),
    ]
    new_events = [
        helpers.new_workflow_started_event(timestamp=current_timestamp),
        helpers.new_child_workflow_failed_event(1, ValueError('child failed')),
    ]
    executor = worker._OrchestrationExecutor(registry, TEST_LOGGER)
    result = executor.execute(TEST_INSTANCE_ID, old_events, new_events)
    actions = result.actions
    assert len(actions) == 1
    assert actions[0].HasField('createTimer')
    retry_timer_1 = actions[0].createTimer
    assert retry_timer_1.childWorkflowRetry.instanceId == expected_first_child_id

    # Timer fires -> new child sub-orch(id=3) with a DIFFERENT instance_id
    old_events = old_events + new_events
    current_timestamp = current_timestamp + timedelta(seconds=1)
    new_events = [
        helpers.new_workflow_started_event(current_timestamp),
        helpers.new_timer_created_event(2, current_timestamp),
        helpers.new_timer_fired_event(2, current_timestamp),
    ]
    executor = worker._OrchestrationExecutor(registry, TEST_LOGGER)
    result = executor.execute(TEST_INSTANCE_ID, old_events, new_events)
    actions = result.actions
    assert len(actions) == 1
    assert actions[0].HasField('createChildWorkflow')

    # Second child fails. Simulate the second child having a DIFFERENT instance ID
    # (e.g. if a backend assigned a new ID on retry) to prove the timer origin still
    # references the FIRST child's ID regardless.
    expected_second_child_id = f'{TEST_INSTANCE_ID}:0003'
    old_events = old_events + new_events
    new_events = [
        helpers.new_workflow_started_event(current_timestamp),
        helpers.new_child_workflow_created_event(3, 'child_orchestrator', expected_second_child_id),
        helpers.new_child_workflow_failed_event(3, ValueError('child failed')),
    ]
    executor = worker._OrchestrationExecutor(registry, TEST_LOGGER)
    result = executor.execute(TEST_INSTANCE_ID, old_events, new_events)
    actions = result.actions
    assert len(actions) == 1
    assert actions[0].HasField('createTimer')
    retry_timer_2 = actions[0].createTimer

    # Retry timer 2 must ALSO point to the FIRST child's instance ID,
    # NOT the second child's ID.
    assert retry_timer_2.childWorkflowRetry.instanceId == expected_first_child_id
    assert retry_timer_2.childWorkflowRetry.instanceId != expected_second_child_id


def get_and_validate_single_complete_workflow_action(
    actions: list[pb.WorkflowAction],
) -> pb.CompleteWorkflowAction:
    assert len(actions) == 1
    assert type(actions[0]) is pb.WorkflowAction
    assert actions[0].HasField('completeWorkflow')
    return actions[0].completeWorkflow
