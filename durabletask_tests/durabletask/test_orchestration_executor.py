# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

import json
import logging
from datetime import datetime, timedelta, timezone

import pytest

import durabletask.internal.helpers as helpers
import durabletask.internal.orchestrator_service_pb2 as pb
from durabletask import task, worker

logging.basicConfig(
    format="%(asctime)s.%(msecs)03d %(name)s %(levelname)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    level=logging.DEBUG,
)
TEST_LOGGER = logging.getLogger("tests")

TEST_INSTANCE_ID = "abc123"


def test_orchestrator_inputs():
    """Validates orchestrator function input population"""

    def orchestrator(ctx: task.OrchestrationContext, my_input: int):
        return my_input, ctx.instance_id, str(ctx.current_utc_datetime), ctx.is_replaying

    test_input = 42

    registry = worker._Registry()
    name = registry.add_orchestrator(orchestrator)

    start_time = datetime.now()
    new_events = [
        helpers.new_orchestrator_started_event(start_time),
        helpers.new_execution_started_event(
            name, TEST_INSTANCE_ID, encoded_input=json.dumps(test_input)
        ),
    ]
    executor = worker._OrchestrationExecutor(registry, TEST_LOGGER)
    result = executor.execute(TEST_INSTANCE_ID, [], new_events)
    actions = result.actions

    complete_action = get_and_validate_single_complete_orchestration_action(actions)
    assert complete_action.orchestrationStatus == pb.ORCHESTRATION_STATUS_COMPLETED
    assert complete_action.result is not None

    expected_output = [test_input, TEST_INSTANCE_ID, str(start_time), False]
    assert complete_action.result.value == json.dumps(expected_output)


def test_complete_orchestration_actions():
    """Tests the actions output for a completed orchestration"""

    def empty_orchestrator(ctx: task.OrchestrationContext, _):
        return "done"

    registry = worker._Registry()
    name = registry.add_orchestrator(empty_orchestrator)

    new_events = [helpers.new_execution_started_event(name, TEST_INSTANCE_ID, encoded_input=None)]
    executor = worker._OrchestrationExecutor(registry, TEST_LOGGER)
    result = executor.execute(TEST_INSTANCE_ID, [], new_events)
    actions = result.actions

    complete_action = get_and_validate_single_complete_orchestration_action(actions)
    assert complete_action.orchestrationStatus == pb.ORCHESTRATION_STATUS_COMPLETED
    assert complete_action.result.value == '"done"'  # results are JSON-encoded


def test_orchestrator_not_registered():
    """Tests the effect of scheduling an unregistered orchestrator"""

    registry = worker._Registry()
    name = "Bogus"
    new_events = [helpers.new_execution_started_event(name, TEST_INSTANCE_ID, encoded_input=None)]
    executor = worker._OrchestrationExecutor(registry, TEST_LOGGER)
    result = executor.execute(TEST_INSTANCE_ID, [], new_events)
    actions = result.actions

    complete_action = get_and_validate_single_complete_orchestration_action(actions)
    assert complete_action.orchestrationStatus == pb.ORCHESTRATION_STATUS_FAILED
    assert complete_action.failureDetails.errorType == "OrchestratorNotRegisteredError"
    assert complete_action.failureDetails.errorMessage


def test_create_timer_actions():
    """Tests the actions output for the create_timer orchestrator method"""

    def delay_orchestrator(ctx: task.OrchestrationContext, _):
        due_time = ctx.current_utc_datetime + timedelta(seconds=1)
        yield ctx.create_timer(due_time)
        return "done"

    registry = worker._Registry()
    name = registry.add_orchestrator(delay_orchestrator)

    start_time = datetime(2020, 1, 1, 12, 0, 0)
    expected_fire_at = start_time + timedelta(seconds=1)

    new_events = [
        helpers.new_orchestrator_started_event(start_time),
        helpers.new_execution_started_event(name, TEST_INSTANCE_ID, encoded_input=None),
    ]
    executor = worker._OrchestrationExecutor(registry, TEST_LOGGER)
    result = executor.execute(TEST_INSTANCE_ID, [], new_events)
    actions = result.actions

    assert actions is not None
    assert len(actions) == 1
    assert type(actions[0]) is pb.OrchestratorAction
    assert actions[0].id == 1
    assert actions[0].HasField("createTimer")
    assert actions[0].createTimer.fireAt.ToDatetime() == expected_fire_at


def test_timer_fired_completion():
    """Tests the resumption of task using a timer_fired event"""

    def delay_orchestrator(ctx: task.OrchestrationContext, _):
        due_time = ctx.current_utc_datetime + timedelta(seconds=1)
        yield ctx.create_timer(due_time)
        return "done"

    registry = worker._Registry()
    name = registry.add_orchestrator(delay_orchestrator)

    start_time = datetime(2020, 1, 1, 12, 0, 0)
    expected_fire_at = start_time + timedelta(seconds=1)

    old_events = [
        helpers.new_orchestrator_started_event(start_time),
        helpers.new_execution_started_event(name, TEST_INSTANCE_ID, encoded_input=None),
        helpers.new_timer_created_event(1, expected_fire_at),
    ]
    new_events = [helpers.new_timer_fired_event(1, expected_fire_at)]

    executor = worker._OrchestrationExecutor(registry, TEST_LOGGER)
    result = executor.execute(TEST_INSTANCE_ID, old_events, new_events)
    actions = result.actions

    complete_action = get_and_validate_single_complete_orchestration_action(actions)
    assert complete_action.orchestrationStatus == pb.ORCHESTRATION_STATUS_COMPLETED
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
        helpers.new_orchestrator_started_event(),
        helpers.new_execution_started_event(name, TEST_INSTANCE_ID, encoded_input),
    ]
    executor = worker._OrchestrationExecutor(registry, TEST_LOGGER)
    result = executor.execute(TEST_INSTANCE_ID, [], new_events)
    actions = result.actions

    assert len(actions) == 1
    assert type(actions[0]) is pb.OrchestratorAction
    assert actions[0].id == 1
    assert actions[0].HasField("scheduleTask")
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
    exec_evt.router.sourceAppID = "source-app"

    new_events = [
        helpers.new_orchestrator_started_event(),
        exec_evt,
    ]

    executor = worker._OrchestrationExecutor(registry, TEST_LOGGER)
    result = executor.execute(TEST_INSTANCE_ID, [], new_events)
    actions = result.actions

    assert len(actions) == 1
    action = actions[0]
    assert action.router.sourceAppID == "source-app"
    assert action.router.targetAppID == ""
    assert action.scheduleTask.router.sourceAppID == "source-app"
    assert action.scheduleTask.router.targetAppID == ""


def test_schedule_activity_actions_router_with_app_id():
    """Tests that scheduleTask action contains correct router fields when app_id is specified"""

    def dummy_activity(ctx, _):
        pass

    def orchestrator(ctx: task.OrchestrationContext, _):
        yield ctx.call_activity(dummy_activity, input=42, app_id="target-app")

    registry = worker._Registry()
    name = registry.add_orchestrator(orchestrator)

    # Prepare execution started event with source app set on router
    exec_evt = helpers.new_execution_started_event(name, TEST_INSTANCE_ID, encoded_input=None)
    exec_evt.router.sourceAppID = "source-app"

    new_events = [
        helpers.new_orchestrator_started_event(),
        exec_evt,
    ]

    executor = worker._OrchestrationExecutor(registry, TEST_LOGGER)
    result = executor.execute(TEST_INSTANCE_ID, [], new_events)
    actions = result.actions

    assert len(actions) == 1
    action = actions[0]
    assert action.router.sourceAppID == "source-app"
    assert action.router.targetAppID == "target-app"
    assert action.scheduleTask.router.sourceAppID == "source-app"
    assert action.scheduleTask.router.targetAppID == "target-app"


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
        helpers.new_orchestrator_started_event(),
        helpers.new_execution_started_event(name, TEST_INSTANCE_ID, encoded_input=None),
        helpers.new_task_scheduled_event(1, task.get_name(dummy_activity)),
    ]

    encoded_output = json.dumps("done!")
    new_events = [helpers.new_task_completed_event(1, encoded_output)]

    executor = worker._OrchestrationExecutor(registry, TEST_LOGGER)
    result = executor.execute(TEST_INSTANCE_ID, old_events, new_events)
    actions = result.actions

    complete_action = get_and_validate_single_complete_orchestration_action(actions)
    assert complete_action.orchestrationStatus == pb.ORCHESTRATION_STATUS_COMPLETED
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
        helpers.new_orchestrator_started_event(),
        helpers.new_execution_started_event(name, TEST_INSTANCE_ID, encoded_input=None),
        helpers.new_task_scheduled_event(1, task.get_name(dummy_activity)),
    ]

    ex = Exception("Kah-BOOOOM!!!")
    new_events = [helpers.new_task_failed_event(1, ex)]

    executor = worker._OrchestrationExecutor(registry, TEST_LOGGER)
    result = executor.execute(TEST_INSTANCE_ID, old_events, new_events)
    actions = result.actions

    complete_action = get_and_validate_single_complete_orchestration_action(actions)
    assert complete_action.orchestrationStatus == pb.ORCHESTRATION_STATUS_FAILED
    assert (
        complete_action.failureDetails.errorType == "TaskFailedError"
    )  # TODO: Should this be the specific error?
    assert str(ex) in complete_action.failureDetails.errorMessage

    # Make sure the line of code where the exception was raised is included in the stack trace
    user_code_statement = "ctx.call_activity(dummy_activity, input=orchestrator_input)"
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
        raise ValueError("Kah-BOOOOM!!!")

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
        helpers.new_orchestrator_started_event(timestamp=current_timestamp),
        helpers.new_execution_started_event(name, TEST_INSTANCE_ID, encoded_input=None),
        helpers.new_task_scheduled_event(1, task.get_name(dummy_activity)),
    ]
    expected_fire_at = current_timestamp + timedelta(seconds=1)

    new_events = [
        helpers.new_orchestrator_started_event(timestamp=current_timestamp),
        helpers.new_task_failed_event(1, ValueError("Kah-BOOOOM!!!")),
    ]
    executor = worker._OrchestrationExecutor(registry, TEST_LOGGER)
    result = executor.execute(TEST_INSTANCE_ID, old_events, new_events)
    actions = result.actions
    assert len(actions) == 1
    assert actions[0].HasField("createTimer")
    assert actions[0].createTimer.fireAt.ToDatetime() == expected_fire_at
    assert actions[0].id == 2

    # --- Timer fires, retry schedules scheduleTask(id=3) ---
    current_timestamp = expected_fire_at
    old_events = old_events + new_events
    new_events = [
        helpers.new_orchestrator_started_event(current_timestamp),
        helpers.new_timer_created_event(2, current_timestamp),
        helpers.new_timer_fired_event(2, current_timestamp),
    ]
    executor = worker._OrchestrationExecutor(registry, TEST_LOGGER)
    result = executor.execute(TEST_INSTANCE_ID, old_events, new_events)
    actions = result.actions
    assert len(actions) == 1
    assert actions[0].HasField("scheduleTask")
    assert actions[0].id == 3  # NEW sequence number for retry
    # Capture the taskExecutionId from first retry - it must be non-empty
    # and consistent across ALL retry attempts
    retry_task_execution_id = actions[0].scheduleTask.taskExecutionId
    assert retry_task_execution_id != "", "taskExecutionId must be non-empty"

    # --- Attempt 2: scheduleTask(id=3) fails ---
    old_events = old_events + new_events
    expected_fire_at = current_timestamp + timedelta(seconds=2)
    new_events = [
        helpers.new_orchestrator_started_event(current_timestamp),
        helpers.new_task_scheduled_event(3, task.get_name(dummy_activity)),
        helpers.new_task_failed_event(3, ValueError("Kah-BOOOOM!!!")),
    ]
    executor = worker._OrchestrationExecutor(registry, TEST_LOGGER)
    result = executor.execute(TEST_INSTANCE_ID, old_events, new_events)
    actions = result.actions
    assert len(actions) == 1
    assert actions[0].HasField("createTimer")
    assert actions[0].createTimer.fireAt.ToDatetime() == expected_fire_at
    assert actions[0].id == 4

    # --- Timer fires, retry schedules scheduleTask(id=5) ---
    current_timestamp = expected_fire_at
    old_events = old_events + new_events
    new_events = [
        helpers.new_orchestrator_started_event(current_timestamp),
        helpers.new_timer_created_event(4, current_timestamp),
        helpers.new_timer_fired_event(4, current_timestamp),
    ]
    executor = worker._OrchestrationExecutor(registry, TEST_LOGGER)
    result = executor.execute(TEST_INSTANCE_ID, old_events, new_events)
    actions = result.actions
    assert len(actions) == 1
    assert actions[0].HasField("scheduleTask")
    assert actions[0].id == 5
    assert actions[0].scheduleTask.taskExecutionId == retry_task_execution_id

    # --- Attempt 3: scheduleTask(id=5) fails ---
    expected_fire_at = current_timestamp + timedelta(seconds=4)
    old_events = old_events + new_events
    new_events = [
        helpers.new_orchestrator_started_event(current_timestamp),
        helpers.new_task_scheduled_event(5, task.get_name(dummy_activity)),
        helpers.new_task_failed_event(5, ValueError("Kah-BOOOOM!!!")),
    ]
    executor = worker._OrchestrationExecutor(registry, TEST_LOGGER)
    result = executor.execute(TEST_INSTANCE_ID, old_events, new_events)
    actions = result.actions
    assert len(actions) == 1
    assert actions[0].HasField("createTimer")
    assert actions[0].createTimer.fireAt.ToDatetime() == expected_fire_at
    assert actions[0].id == 6

    # --- Timer fires, retry schedules scheduleTask(id=7) ---
    current_timestamp = expected_fire_at
    old_events = old_events + new_events
    new_events = [
        helpers.new_orchestrator_started_event(current_timestamp),
        helpers.new_timer_created_event(6, current_timestamp),
        helpers.new_timer_fired_event(6, current_timestamp),
    ]
    executor = worker._OrchestrationExecutor(registry, TEST_LOGGER)
    result = executor.execute(TEST_INSTANCE_ID, old_events, new_events)
    actions = result.actions
    assert len(actions) == 1
    assert actions[0].HasField("scheduleTask")
    assert actions[0].id == 7
    assert actions[0].scheduleTask.taskExecutionId == retry_task_execution_id

    # --- Attempt 4: scheduleTask(id=7) fails ---
    expected_fire_at = current_timestamp + timedelta(seconds=8)
    old_events = old_events + new_events
    new_events = [
        helpers.new_orchestrator_started_event(current_timestamp),
        helpers.new_task_scheduled_event(7, task.get_name(dummy_activity)),
        helpers.new_task_failed_event(7, ValueError("Kah-BOOOOM!!!")),
    ]
    executor = worker._OrchestrationExecutor(registry, TEST_LOGGER)
    result = executor.execute(TEST_INSTANCE_ID, old_events, new_events)
    actions = result.actions
    assert len(actions) == 1
    assert actions[0].HasField("createTimer")
    assert actions[0].createTimer.fireAt.ToDatetime() == expected_fire_at
    assert actions[0].id == 8

    # --- Timer fires, retry schedules scheduleTask(id=9) ---
    current_timestamp = expected_fire_at
    old_events = old_events + new_events
    new_events = [
        helpers.new_orchestrator_started_event(current_timestamp),
        helpers.new_timer_created_event(8, current_timestamp),
        helpers.new_timer_fired_event(8, current_timestamp),
    ]
    executor = worker._OrchestrationExecutor(registry, TEST_LOGGER)
    result = executor.execute(TEST_INSTANCE_ID, old_events, new_events)
    actions = result.actions
    assert len(actions) == 1
    assert actions[0].HasField("scheduleTask")
    assert actions[0].id == 9
    assert actions[0].scheduleTask.taskExecutionId == retry_task_execution_id

    # --- Attempt 5: scheduleTask(id=9) fails ---
    # max_retry_interval caps at 10 seconds (instead of 16)
    expected_fire_at = current_timestamp + timedelta(seconds=10)
    old_events = old_events + new_events
    new_events = [
        helpers.new_orchestrator_started_event(current_timestamp),
        helpers.new_task_scheduled_event(9, task.get_name(dummy_activity)),
        helpers.new_task_failed_event(9, ValueError("Kah-BOOOOM!!!")),
    ]
    executor = worker._OrchestrationExecutor(registry, TEST_LOGGER)
    result = executor.execute(TEST_INSTANCE_ID, old_events, new_events)
    actions = result.actions
    assert len(actions) == 1
    assert actions[0].HasField("createTimer")
    assert actions[0].createTimer.fireAt.ToDatetime() == expected_fire_at
    assert actions[0].id == 10

    # --- Timer fires, retry schedules scheduleTask(id=11) ---
    current_timestamp = expected_fire_at
    old_events = old_events + new_events
    new_events = [
        helpers.new_orchestrator_started_event(current_timestamp),
        helpers.new_timer_created_event(10, current_timestamp),
        helpers.new_timer_fired_event(10, current_timestamp),
    ]
    executor = worker._OrchestrationExecutor(registry, TEST_LOGGER)
    result = executor.execute(TEST_INSTANCE_ID, old_events, new_events)
    actions = result.actions
    assert len(actions) == 1
    assert actions[0].HasField("scheduleTask")
    assert actions[0].id == 11
    assert actions[0].scheduleTask.taskExecutionId == retry_task_execution_id

    # --- Attempt 6: scheduleTask(id=11) fails - max attempts exhausted ---
    old_events = old_events + new_events
    new_events = [
        helpers.new_orchestrator_started_event(current_timestamp),
        helpers.new_task_scheduled_event(11, task.get_name(dummy_activity)),
        helpers.new_task_failed_event(11, ValueError("Kah-BOOOOM!!!")),
    ]
    executor = worker._OrchestrationExecutor(registry, TEST_LOGGER)
    result = executor.execute(TEST_INSTANCE_ID, old_events, new_events)
    actions = result.actions
    assert len(actions) == 1
    assert actions[0].completeOrchestration.failureDetails.errorMessage.__contains__(
        "Activity task #11 failed: Kah-BOOOOM!!!"
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
        helpers.new_orchestrator_started_event(),
        helpers.new_execution_started_event(name, TEST_INSTANCE_ID, encoded_input=None),
        helpers.new_timer_created_event(1, fire_at),
    ]
    new_events = [helpers.new_timer_fired_event(timer_id=1, fire_at=fire_at)]

    executor = worker._OrchestrationExecutor(registry, TEST_LOGGER)
    result = executor.execute(TEST_INSTANCE_ID, old_events, new_events)
    actions = result.actions

    complete_action = get_and_validate_single_complete_orchestration_action(actions)
    assert complete_action.orchestrationStatus == pb.ORCHESTRATION_STATUS_FAILED
    assert complete_action.failureDetails.errorType == "NonDeterminismError"
    assert "1" in complete_action.failureDetails.errorMessage  # task ID
    assert "create_timer" in complete_action.failureDetails.errorMessage  # expected method name
    assert "call_activity" in complete_action.failureDetails.errorMessage  # actual method name


def test_nondeterminism_expected_activity_call_no_task_id():
    """Tests the non-determinism detection logic when invoking activity functions"""

    def orchestrator(ctx: task.OrchestrationContext, _):
        result = yield task.CompletableTask()  # dummy task
        return result

    registry = worker._Registry()
    name = registry.add_orchestrator(orchestrator)

    old_events = [
        helpers.new_orchestrator_started_event(),
        helpers.new_execution_started_event(name, TEST_INSTANCE_ID, encoded_input=None),
        helpers.new_task_scheduled_event(1, "bogus_activity"),
    ]

    new_events = [helpers.new_task_completed_event(1)]

    executor = worker._OrchestrationExecutor(registry, TEST_LOGGER)
    result = executor.execute(TEST_INSTANCE_ID, old_events, new_events)
    actions = result.actions

    complete_action = get_and_validate_single_complete_orchestration_action(actions)
    assert complete_action.orchestrationStatus == pb.ORCHESTRATION_STATUS_FAILED
    assert complete_action.failureDetails.errorType == "NonDeterminismError"
    assert "1" in complete_action.failureDetails.errorMessage  # task ID
    assert "call_activity" in complete_action.failureDetails.errorMessage  # expected method name


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
        helpers.new_orchestrator_started_event(),
        helpers.new_execution_started_event(name, TEST_INSTANCE_ID, encoded_input=None),
        helpers.new_task_scheduled_event(1, task.get_name(dummy_activity)),
    ]

    new_events = [helpers.new_task_completed_event(1)]

    executor = worker._OrchestrationExecutor(registry, TEST_LOGGER)
    result = executor.execute(TEST_INSTANCE_ID, old_events, new_events)
    actions = result.actions

    complete_action = get_and_validate_single_complete_orchestration_action(actions)
    assert complete_action.orchestrationStatus == pb.ORCHESTRATION_STATUS_FAILED
    assert complete_action.failureDetails.errorType == "NonDeterminismError"
    assert "1" in complete_action.failureDetails.errorMessage  # task ID
    assert "call_activity" in complete_action.failureDetails.errorMessage  # expected method name
    assert "create_timer" in complete_action.failureDetails.errorMessage  # unexpected method name


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
        helpers.new_orchestrator_started_event(),
        helpers.new_execution_started_event(name, TEST_INSTANCE_ID, encoded_input=None),
        helpers.new_task_scheduled_event(1, "original_activity"),
    ]

    new_events = [helpers.new_task_completed_event(1)]

    executor = worker._OrchestrationExecutor(registry, TEST_LOGGER)
    result = executor.execute(TEST_INSTANCE_ID, old_events, new_events)
    actions = result.actions

    complete_action = get_and_validate_single_complete_orchestration_action(actions)
    assert complete_action.orchestrationStatus == pb.ORCHESTRATION_STATUS_FAILED
    assert complete_action.failureDetails.errorType == "NonDeterminismError"
    assert "1" in complete_action.failureDetails.errorMessage  # task ID
    assert "call_activity" in complete_action.failureDetails.errorMessage  # expected method name
    assert (
        "original_activity" in complete_action.failureDetails.errorMessage
    )  # expected activity name
    assert (
        "dummy_activity" in complete_action.failureDetails.errorMessage
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
        helpers.new_orchestrator_started_event(),
        helpers.new_execution_started_event(
            orchestrator_name, TEST_INSTANCE_ID, encoded_input=None
        ),
        helpers.new_sub_orchestration_created_event(
            1, suborchestrator_name, "sub-orch-123", encoded_input=None
        ),
    ]

    new_events = [helpers.new_sub_orchestration_completed_event(1, encoded_output="42")]

    executor = worker._OrchestrationExecutor(registry, TEST_LOGGER)
    result = executor.execute(TEST_INSTANCE_ID, old_events, new_events)
    actions = result.actions

    complete_action = get_and_validate_single_complete_orchestration_action(actions)
    assert complete_action.orchestrationStatus == pb.ORCHESTRATION_STATUS_COMPLETED
    assert complete_action.result.value == "42"


def test_create_sub_orchestration_actions_router_without_app_id():
    """Tests that createSubOrchestration action contains correct router fields when app_id is specified"""

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
    exec_evt.router.sourceAppID = "source-app"

    new_events = [
        helpers.new_orchestrator_started_event(),
        exec_evt,
    ]

    executor = worker._OrchestrationExecutor(registry, TEST_LOGGER)
    result = executor.execute(TEST_INSTANCE_ID, [], new_events)
    actions = result.actions

    assert len(actions) == 1
    action = actions[0]
    assert action.router.sourceAppID == "source-app"
    assert action.router.targetAppID == ""
    assert action.createSubOrchestration.router.sourceAppID == "source-app"
    assert action.createSubOrchestration.router.targetAppID == ""


def test_create_sub_orchestration_actions_router_with_app_id():
    """Tests that createSubOrchestration action contains correct router fields when app_id is specified"""

    def suborchestrator(ctx: task.OrchestrationContext, _):
        pass

    def orchestrator(ctx: task.OrchestrationContext, _):
        yield ctx.call_sub_orchestrator(suborchestrator, input=None, app_id="target-app")

    registry = worker._Registry()
    registry.add_orchestrator(suborchestrator)
    orchestrator_name = registry.add_orchestrator(orchestrator)

    exec_evt = helpers.new_execution_started_event(
        orchestrator_name, TEST_INSTANCE_ID, encoded_input=None
    )
    exec_evt.router.sourceAppID = "source-app"

    new_events = [
        helpers.new_orchestrator_started_event(),
        exec_evt,
    ]

    executor = worker._OrchestrationExecutor(registry, TEST_LOGGER)
    result = executor.execute(TEST_INSTANCE_ID, [], new_events)
    actions = result.actions

    assert len(actions) == 1
    action = actions[0]
    assert action.router.sourceAppID == "source-app"
    assert action.router.targetAppID == "target-app"
    assert action.createSubOrchestration.router.sourceAppID == "source-app"
    assert action.createSubOrchestration.router.targetAppID == "target-app"


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
        helpers.new_orchestrator_started_event(),
        helpers.new_execution_started_event(
            orchestrator_name, TEST_INSTANCE_ID, encoded_input=None
        ),
        helpers.new_sub_orchestration_created_event(
            1, suborchestrator_name, "sub-orch-123", encoded_input=None
        ),
    ]

    ex = Exception("Kah-BOOOOM!!!")
    new_events = [helpers.new_sub_orchestration_failed_event(1, ex)]

    executor = worker._OrchestrationExecutor(registry, TEST_LOGGER)
    result = executor.execute(TEST_INSTANCE_ID, old_events, new_events)
    actions = result.actions

    complete_action = get_and_validate_single_complete_orchestration_action(actions)
    assert complete_action.orchestrationStatus == pb.ORCHESTRATION_STATUS_FAILED
    assert (
        complete_action.failureDetails.errorType == "TaskFailedError"
    )  # TODO: Should this be the specific error?
    assert str(ex) in complete_action.failureDetails.errorMessage

    # Make sure the line of code where the exception was raised is included in the stack trace
    user_code_statement = "ctx.call_sub_orchestrator(suborchestrator)"
    assert user_code_statement in complete_action.failureDetails.stackTrace.value


def test_nondeterminism_expected_sub_orchestration_task_completion_no_task():
    """Tests the non-determinism detection when a sub-orchestration action is encounteed when it shouldn't be"""

    def orchestrator(ctx: task.OrchestrationContext, _):
        result = yield task.CompletableTask()  # dummy task
        return result

    registry = worker._Registry()
    orchestrator_name = registry.add_orchestrator(orchestrator)

    old_events = [
        helpers.new_orchestrator_started_event(),
        helpers.new_execution_started_event(
            orchestrator_name, TEST_INSTANCE_ID, encoded_input=None
        ),
        helpers.new_sub_orchestration_created_event(
            1, "some_sub_orchestration", "sub-orch-123", encoded_input=None
        ),
    ]

    new_events = [helpers.new_sub_orchestration_completed_event(1, encoded_output="42")]

    executor = worker._OrchestrationExecutor(registry, TEST_LOGGER)
    result = executor.execute(TEST_INSTANCE_ID, old_events, new_events)
    actions = result.actions

    complete_action = get_and_validate_single_complete_orchestration_action(actions)
    assert complete_action.orchestrationStatus == pb.ORCHESTRATION_STATUS_FAILED
    assert complete_action.failureDetails.errorType == "NonDeterminismError"
    assert "1" in complete_action.failureDetails.errorMessage  # task ID
    assert (
        "call_sub_orchestrator" in complete_action.failureDetails.errorMessage
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
        helpers.new_orchestrator_started_event(),
        helpers.new_execution_started_event(
            orchestrator_name, TEST_INSTANCE_ID, encoded_input=None
        ),
        helpers.new_sub_orchestration_created_event(
            1, "some_sub_orchestration", "sub-orch-123", encoded_input=None
        ),
    ]

    new_events = [helpers.new_sub_orchestration_completed_event(1, encoded_output="42")]

    executor = worker._OrchestrationExecutor(registry, TEST_LOGGER)
    result = executor.execute(TEST_INSTANCE_ID, old_events, new_events)
    actions = result.actions

    complete_action = get_and_validate_single_complete_orchestration_action(actions)
    assert complete_action.orchestrationStatus == pb.ORCHESTRATION_STATUS_FAILED
    assert complete_action.failureDetails.errorType == "NonDeterminismError"
    assert "1" in complete_action.failureDetails.errorMessage  # task ID
    assert (
        "call_sub_orchestrator" in complete_action.failureDetails.errorMessage
    )  # expected method name


def test_raise_event():
    """Tests that an orchestration can wait for and process an external event sent by a client"""

    def orchestrator(ctx: task.OrchestrationContext, _):
        result = yield ctx.wait_for_external_event("my_event")
        return result

    registry = worker._Registry()
    orchestrator_name = registry.add_orchestrator(orchestrator)

    old_events = []
    new_events = [
        helpers.new_orchestrator_started_event(),
        helpers.new_execution_started_event(orchestrator_name, TEST_INSTANCE_ID),
    ]

    # Execute the orchestration until it is waiting for an external event. The result
    # should be an empty list of actions because the orchestration didn't schedule any work.
    executor = worker._OrchestrationExecutor(registry, TEST_LOGGER)
    result = executor.execute(TEST_INSTANCE_ID, old_events, new_events)
    actions = result.actions
    assert len(actions) == 0

    # Now send an external event to the orchestration and execute it again. This time
    # the orchestration should complete.
    old_events = new_events
    new_events = [helpers.new_event_raised_event("my_event", encoded_input="42")]
    executor = worker._OrchestrationExecutor(registry, TEST_LOGGER)
    result = executor.execute(TEST_INSTANCE_ID, old_events, new_events)
    actions = result.actions
    complete_action = get_and_validate_single_complete_orchestration_action(actions)
    assert complete_action.orchestrationStatus == pb.ORCHESTRATION_STATUS_COMPLETED
    assert complete_action.result.value == "42"


def test_raise_event_buffered():
    """Tests that an orchestration can receive an event that arrives earlier than expected"""

    def orchestrator(ctx: task.OrchestrationContext, _):
        yield ctx.create_timer(ctx.current_utc_datetime + timedelta(days=1))
        result = yield ctx.wait_for_external_event("my_event")
        return result

    registry = worker._Registry()
    orchestrator_name = registry.add_orchestrator(orchestrator)

    old_events = []
    new_events = [
        helpers.new_orchestrator_started_event(),
        helpers.new_execution_started_event(orchestrator_name, TEST_INSTANCE_ID),
        helpers.new_event_raised_event("my_event", encoded_input="42"),
    ]

    # Execute the orchestration. It should be in a running state waiting for the timer to fire
    executor = worker._OrchestrationExecutor(registry, TEST_LOGGER)
    result = executor.execute(TEST_INSTANCE_ID, old_events, new_events)
    actions = result.actions
    assert len(actions) == 1
    assert actions[0].HasField("createTimer")

    # Complete the timer task. The orchestration should move to the wait_for_external_event step, which
    # should then complete immediately because the event was buffered in the old event history.
    timer_due_time = datetime.now(timezone.utc) + timedelta(days=1)
    old_events = new_events + [helpers.new_timer_created_event(1, timer_due_time)]
    new_events = [helpers.new_timer_fired_event(1, timer_due_time)]
    executor = worker._OrchestrationExecutor(registry, TEST_LOGGER)
    result = executor.execute(TEST_INSTANCE_ID, old_events, new_events)
    actions = result.actions
    complete_action = get_and_validate_single_complete_orchestration_action(actions)
    assert complete_action.orchestrationStatus == pb.ORCHESTRATION_STATUS_COMPLETED
    assert complete_action.result.value == "42"


def test_suspend_resume():
    """Tests that an orchestration can be suspended and resumed"""

    def orchestrator(ctx: task.OrchestrationContext, _):
        result = yield ctx.wait_for_external_event("my_event")
        return result

    registry = worker._Registry()
    orchestrator_name = registry.add_orchestrator(orchestrator)

    old_events = [
        helpers.new_orchestrator_started_event(),
        helpers.new_execution_started_event(orchestrator_name, TEST_INSTANCE_ID),
    ]
    new_events = [
        helpers.new_suspend_event(),
        helpers.new_event_raised_event("my_event", encoded_input="42"),
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
    complete_action = get_and_validate_single_complete_orchestration_action(actions)
    assert complete_action.orchestrationStatus == pb.ORCHESTRATION_STATUS_COMPLETED
    assert complete_action.result.value == "42"


def test_terminate():
    """Tests that an orchestration can be terminated before it completes"""

    def orchestrator(ctx: task.OrchestrationContext, _):
        result = yield ctx.wait_for_external_event("my_event")
        return result

    registry = worker._Registry()
    orchestrator_name = registry.add_orchestrator(orchestrator)

    old_events = [
        helpers.new_orchestrator_started_event(),
        helpers.new_execution_started_event(orchestrator_name, TEST_INSTANCE_ID),
    ]
    new_events = [
        helpers.new_terminated_event(encoded_output=json.dumps("terminated!")),
        helpers.new_event_raised_event("my_event", encoded_input="42"),
    ]

    # Execute the orchestration. It should be in a running state waiting for an external event
    executor = worker._OrchestrationExecutor(registry, TEST_LOGGER)
    result = executor.execute(TEST_INSTANCE_ID, old_events, new_events)
    actions = result.actions
    complete_action = get_and_validate_single_complete_orchestration_action(actions)
    assert complete_action.orchestrationStatus == pb.ORCHESTRATION_STATUS_TERMINATED
    assert complete_action.result.value == json.dumps("terminated!")


@pytest.mark.parametrize("save_events", [True, False])
def test_continue_as_new(save_events: bool):
    """Tests the behavior of the continue-as-new API"""

    def orchestrator(ctx: task.OrchestrationContext, input: int):
        yield ctx.create_timer(ctx.current_utc_datetime + timedelta(days=1))
        ctx.continue_as_new(input + 1, save_events=save_events)

    registry = worker._Registry()
    orchestrator_name = registry.add_orchestrator(orchestrator)

    old_events = [
        helpers.new_orchestrator_started_event(),
        helpers.new_execution_started_event(orchestrator_name, TEST_INSTANCE_ID, encoded_input="1"),
        helpers.new_event_raised_event("my_event", encoded_input="42"),
        helpers.new_event_raised_event("my_event", encoded_input="43"),
        helpers.new_event_raised_event("my_event", encoded_input="44"),
        helpers.new_timer_created_event(1, datetime.now(timezone.utc) + timedelta(days=1)),
    ]
    new_events = [helpers.new_timer_fired_event(1, datetime.now(timezone.utc) + timedelta(days=1))]

    # Execute the orchestration. It should be in a running state waiting for the timer to fire
    executor = worker._OrchestrationExecutor(registry, TEST_LOGGER)
    result = executor.execute(TEST_INSTANCE_ID, old_events, new_events)
    actions = result.actions
    complete_action = get_and_validate_single_complete_orchestration_action(actions)
    assert complete_action.orchestrationStatus == pb.ORCHESTRATION_STATUS_CONTINUED_AS_NEW
    assert complete_action.result.value == json.dumps(2)
    assert len(complete_action.carryoverEvents) == (3 if save_events else 0)
    for i in range(len(complete_action.carryoverEvents)):
        event = complete_action.carryoverEvents[i]
        assert type(event) is pb.HistoryEvent
        assert event.HasField("eventRaised")
        assert (
            event.eventRaised.name.casefold() == "my_event".casefold()
        )  # event names are case-insensitive
        assert event.eventRaised.input.value == json.dumps(42 + i)


def test_fan_out():
    """Tests that a fan-out pattern correctly schedules N tasks"""

    def hello(_, name: str):
        return f"Hello {name}!"

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
        helpers.new_orchestrator_started_event(),
        helpers.new_execution_started_event(
            orchestrator_name, TEST_INSTANCE_ID, encoded_input="10"
        ),
    ]

    executor = worker._OrchestrationExecutor(registry, TEST_LOGGER)
    result = executor.execute(TEST_INSTANCE_ID, old_events, new_events)
    actions = result.actions

    # The result should be 10 "taskScheduled" actions with inputs from 0 to 9
    assert len(actions) == 10
    for i in range(10):
        assert actions[i].HasField("scheduleTask")
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
        helpers.new_orchestrator_started_event(),
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

    complete_action = get_and_validate_single_complete_orchestration_action(actions)
    assert complete_action.orchestrationStatus == pb.ORCHESTRATION_STATUS_COMPLETED
    assert complete_action.result.value == "[0, 1, 2, 3, 4, 5, 6, 7, 8, 9]"


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
        helpers.new_orchestrator_started_event(),
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
    ex = Exception("Kah-BOOOOM!!!")
    new_events.append(helpers.new_task_failed_event(6, ex))

    # Now test with the full set of new events. We expect the orchestration to complete.
    executor = worker._OrchestrationExecutor(registry, TEST_LOGGER)
    result = executor.execute(TEST_INSTANCE_ID, old_events, new_events)
    actions = result.actions

    complete_action = get_and_validate_single_complete_orchestration_action(actions)
    assert complete_action.orchestrationStatus == pb.ORCHESTRATION_STATUS_FAILED
    assert (
        complete_action.failureDetails.errorType == "TaskFailedError"
    )  # TODO: Is this the right error type?
    assert str(ex) in complete_action.failureDetails.errorMessage


def test_when_any():
    """Tests that a when_any pattern works correctly"""

    def hello(_, name: str):
        return f"Hello {name}!"

    def orchestrator(ctx: task.OrchestrationContext, _):
        t1 = ctx.call_activity(hello, input="Tokyo")
        t2 = ctx.call_activity(hello, input="Seattle")
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
    assert actions[0].HasField("scheduleTask")
    assert actions[1].HasField("scheduleTask")

    # The next tests assume that the orchestration has already awaited at the task.when_any()
    old_events = [
        helpers.new_orchestrator_started_event(),
        helpers.new_execution_started_event(
            orchestrator_name, TEST_INSTANCE_ID, encoded_input=None
        ),
        helpers.new_task_scheduled_event(1, activity_name, encoded_input=json.dumps("Tokyo")),
        helpers.new_task_scheduled_event(2, activity_name, encoded_input=json.dumps("Seattle")),
    ]

    # Test 2: Complete the "Tokyo" task. We expect the orchestration to complete with output "Hello, Tokyo!"
    encoded_output = json.dumps(hello(None, "Tokyo"))
    new_events = [helpers.new_task_completed_event(1, encoded_output)]
    executor = worker._OrchestrationExecutor(registry, TEST_LOGGER)
    result = executor.execute(TEST_INSTANCE_ID, old_events, new_events)
    actions = result.actions
    complete_action = get_and_validate_single_complete_orchestration_action(actions)
    assert complete_action.orchestrationStatus == pb.ORCHESTRATION_STATUS_COMPLETED
    assert complete_action.result.value == encoded_output

    # Test 3: Complete the "Seattle" task. We expect the orchestration to complete with output "Hello, Seattle!"
    encoded_output = json.dumps(hello(None, "Seattle"))
    new_events = [helpers.new_task_completed_event(2, encoded_output)]
    executor = worker._OrchestrationExecutor(registry, TEST_LOGGER)
    result = executor.execute(TEST_INSTANCE_ID, old_events, new_events)
    actions = result.actions
    complete_action = get_and_validate_single_complete_orchestration_action(actions)
    assert complete_action.orchestrationStatus == pb.ORCHESTRATION_STATUS_COMPLETED
    assert complete_action.result.value == encoded_output


def test_when_any_with_retry():
    """Tests that a when_any pattern works correctly with retries"""

    def dummy_activity(_, inp: str):
        if inp == "Tokyo":
            raise ValueError("Kah-BOOOOM!!!")
        return f"Hello {inp}!"

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
            input="Tokyo",
        )
        t2 = ctx.call_activity(dummy_activity, input="Seattle")
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
        helpers.new_orchestrator_started_event(timestamp=current_timestamp),
        helpers.new_execution_started_event(
            orchestrator_name, TEST_INSTANCE_ID, encoded_input=None
        ),
        helpers.new_task_scheduled_event(1, task.get_name(dummy_activity)),
        helpers.new_task_scheduled_event(2, task.get_name(dummy_activity)),
    ]
    expected_fire_at = current_timestamp + timedelta(seconds=1)

    new_events = [
        helpers.new_orchestrator_started_event(timestamp=current_timestamp),
        helpers.new_task_failed_event(1, ValueError("Kah-BOOOOM!!!")),
    ]
    executor = worker._OrchestrationExecutor(registry, TEST_LOGGER)
    result = executor.execute(TEST_INSTANCE_ID, old_events, new_events)
    actions = result.actions
    assert len(actions) == 1
    assert actions[0].HasField("createTimer")
    assert actions[0].createTimer.fireAt.ToDatetime() == expected_fire_at
    assert actions[0].id == 3

    # Simulate the timer firing at the expected time and confirm that another activity task is scheduled
    current_timestamp = expected_fire_at
    old_events = old_events + new_events
    new_events = [
        helpers.new_orchestrator_started_event(current_timestamp),
        helpers.new_timer_created_event(3, current_timestamp),
        helpers.new_timer_fired_event(3, current_timestamp),
    ]
    executor = worker._OrchestrationExecutor(registry, TEST_LOGGER)
    result = executor.execute(TEST_INSTANCE_ID, old_events, new_events)
    actions = result.actions
    assert len(actions) == 1
    assert actions[0].HasField("scheduleTask")
    assert actions[0].id == 4  # New sequence number for retry

    # Simulate the task failing for the second time and confirm that a timer is scheduled for 2 seconds in the future
    old_events = old_events + new_events
    expected_fire_at = current_timestamp + timedelta(seconds=2)
    new_events = [
        helpers.new_orchestrator_started_event(current_timestamp),
        helpers.new_task_scheduled_event(4, task.get_name(dummy_activity)),
        helpers.new_task_failed_event(4, ValueError("Kah-BOOOOM!!!")),
    ]
    executor = worker._OrchestrationExecutor(registry, TEST_LOGGER)
    result = executor.execute(TEST_INSTANCE_ID, old_events, new_events)
    actions = result.actions
    assert len(actions) == 1
    assert actions[0].HasField("createTimer")
    assert actions[0].createTimer.fireAt.ToDatetime() == expected_fire_at
    assert actions[0].id == 5

    # Complete the "Seattle" task. We expect the orchestration to complete with output "Hello, Seattle!"
    encoded_output = json.dumps(dummy_activity(None, "Seattle"))
    new_events = [helpers.new_task_completed_event(2, encoded_output)]
    executor = worker._OrchestrationExecutor(registry, TEST_LOGGER)
    result = executor.execute(TEST_INSTANCE_ID, old_events, new_events)
    actions = result.actions
    complete_action = get_and_validate_single_complete_orchestration_action(actions)
    assert complete_action.orchestrationStatus == pb.ORCHESTRATION_STATUS_COMPLETED
    assert complete_action.result.value == encoded_output


def test_when_all_with_retry():
    """Tests that a when_all pattern works correctly with retries"""

    def dummy_activity(ctx, inp: str):
        if inp == "Tokyo":
            raise ValueError("Kah-BOOOOM!!!")
        return f"Hello {inp}!"

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
            input="Tokyo",
        )
        t2 = ctx.call_activity(dummy_activity, input="Seattle")
        results = yield task.when_all([t1, t2])
        return results

    registry = worker._Registry()
    orchestrator_name = registry.add_orchestrator(orchestrator)
    registry.add_activity(dummy_activity)

    current_timestamp = datetime.utcnow()
    # Simulate the task failing for the first time and confirm that a timer is scheduled for 2 seconds in the future
    old_events = [
        helpers.new_orchestrator_started_event(timestamp=current_timestamp),
        helpers.new_execution_started_event(
            orchestrator_name, TEST_INSTANCE_ID, encoded_input=None
        ),
        helpers.new_task_scheduled_event(1, task.get_name(dummy_activity)),
        helpers.new_task_scheduled_event(2, task.get_name(dummy_activity)),
    ]
    expected_fire_at = current_timestamp + timedelta(seconds=2)

    new_events = [
        helpers.new_orchestrator_started_event(timestamp=current_timestamp),
        helpers.new_task_failed_event(1, ValueError("Kah-BOOOOM!!!")),
    ]
    executor = worker._OrchestrationExecutor(registry, TEST_LOGGER)
    result = executor.execute(TEST_INSTANCE_ID, old_events, new_events)
    actions = result.actions
    assert len(actions) == 1
    assert actions[0].HasField("createTimer")
    assert actions[0].createTimer.fireAt.ToDatetime() == expected_fire_at
    assert actions[0].id == 3

    # Simulate the timer firing at the expected time and confirm that another activity task is scheduled
    current_timestamp = expected_fire_at
    old_events = old_events + new_events
    new_events = [
        helpers.new_orchestrator_started_event(current_timestamp),
        helpers.new_timer_created_event(3, current_timestamp),
        helpers.new_timer_fired_event(3, current_timestamp),
    ]
    executor = worker._OrchestrationExecutor(registry, TEST_LOGGER)
    result = executor.execute(TEST_INSTANCE_ID, old_events, new_events)
    actions = result.actions
    assert len(actions) == 1
    assert actions[0].HasField("scheduleTask")
    assert actions[0].id == 4  # New sequence number for retry

    # Simulate the task failing for the second time and confirm that a timer is scheduled for 5 seconds in the future
    old_events = old_events + new_events
    expected_fire_at = current_timestamp + timedelta(seconds=5)
    new_events = [
        helpers.new_orchestrator_started_event(current_timestamp),
        helpers.new_task_scheduled_event(4, task.get_name(dummy_activity)),
        helpers.new_task_failed_event(4, ValueError("Kah-BOOOOM!!!")),
    ]
    executor = worker._OrchestrationExecutor(registry, TEST_LOGGER)
    result = executor.execute(TEST_INSTANCE_ID, old_events, new_events)
    actions = result.actions
    assert len(actions) == 1
    assert actions[0].HasField("createTimer")
    assert actions[0].createTimer.fireAt.ToDatetime() == expected_fire_at
    assert actions[0].id == 5

    # Complete the "Seattle" task.
    # And, Simulate the timer firing at the expected time and confirm that another activity task is scheduled
    encoded_output = json.dumps(dummy_activity(None, "Seattle"))
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
    assert actions[0].HasField("scheduleTask")
    assert actions[0].id == 6  # New sequence number for retry

    ex = ValueError("Kah-BOOOOM!!!")

    # Simulate the task failing for the third time. Overall workflow should fail at this point.
    old_events = old_events + new_events
    new_events = [
        helpers.new_orchestrator_started_event(current_timestamp),
        helpers.new_task_scheduled_event(6, task.get_name(dummy_activity)),
        helpers.new_task_failed_event(6, ValueError("Kah-BOOOOM!!!")),
    ]
    executor = worker._OrchestrationExecutor(registry, TEST_LOGGER)
    result = executor.execute(TEST_INSTANCE_ID, old_events, new_events)
    actions = result.actions
    complete_action = get_and_validate_single_complete_orchestration_action(actions)
    assert complete_action.orchestrationStatus == pb.ORCHESTRATION_STATUS_FAILED
    assert (
        complete_action.failureDetails.errorType == "TaskFailedError"
    )  # TODO: Should this be the specific error?
    assert str(ex) in complete_action.failureDetails.errorMessage


def test_activity_non_retryable_default_exception():
    """If activity fails with NonRetryableError, it should not be retried and orchestration should fail immediately."""

    def dummy_activity(ctx, _):
        raise task.NonRetryableError("boom")

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
        helpers.new_orchestrator_started_event(timestamp=current_timestamp),
        helpers.new_execution_started_event(name, TEST_INSTANCE_ID, encoded_input=None),
        helpers.new_task_scheduled_event(1, task.get_name(dummy_activity)),
    ]
    new_events = [
        helpers.new_orchestrator_started_event(timestamp=current_timestamp),
        helpers.new_task_failed_event(1, task.NonRetryableError("boom")),
    ]

    executor = worker._OrchestrationExecutor(registry, TEST_LOGGER)
    result = executor.execute(TEST_INSTANCE_ID, old_events, new_events)
    actions = result.actions
    complete_action = get_and_validate_single_complete_orchestration_action(actions)
    assert complete_action.orchestrationStatus == pb.ORCHESTRATION_STATUS_FAILED
    assert complete_action.failureDetails.errorMessage.__contains__("Activity task #1 failed: boom")


def test_activity_non_retryable_policy_name():
    """If policy marks ValueError as non-retryable (by name), fail immediately without retry."""

    def dummy_activity(ctx, _):
        raise ValueError("boom")

    def orchestrator(ctx: task.OrchestrationContext, _):
        yield ctx.call_activity(
            dummy_activity,
            retry_policy=task.RetryPolicy(
                first_retry_interval=timedelta(seconds=1),
                max_number_of_attempts=5,
                non_retryable_error_types=["ValueError"],
            ),
        )

    registry = worker._Registry()
    name = registry.add_orchestrator(orchestrator)

    current_timestamp = datetime.utcnow()
    old_events = [
        helpers.new_orchestrator_started_event(timestamp=current_timestamp),
        helpers.new_execution_started_event(name, TEST_INSTANCE_ID, encoded_input=None),
        helpers.new_task_scheduled_event(1, task.get_name(dummy_activity)),
    ]
    new_events = [
        helpers.new_orchestrator_started_event(timestamp=current_timestamp),
        helpers.new_task_failed_event(1, ValueError("boom")),
    ]

    executor = worker._OrchestrationExecutor(registry, TEST_LOGGER)
    result = executor.execute(TEST_INSTANCE_ID, old_events, new_events)
    actions = result.actions
    complete_action = get_and_validate_single_complete_orchestration_action(actions)
    assert complete_action.orchestrationStatus == pb.ORCHESTRATION_STATUS_FAILED
    assert complete_action.failureDetails.errorMessage.__contains__("Activity task #1 failed: boom")


def test_activity_generic_exception_is_retryable():
    """Verify that generic Exception is retryable by default (not treated as non-retryable)."""

    def dummy_activity(ctx, _):
        raise Exception("generic error")

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
        helpers.new_orchestrator_started_event(timestamp=current_timestamp),
        helpers.new_execution_started_event(name, TEST_INSTANCE_ID, encoded_input=None),
        helpers.new_task_scheduled_event(1, task.get_name(dummy_activity)),
    ]
    new_events = [
        helpers.new_orchestrator_started_event(timestamp=current_timestamp),
        helpers.new_task_failed_event(1, Exception("generic error")),
    ]

    executor = worker._OrchestrationExecutor(registry, TEST_LOGGER)
    result = executor.execute(TEST_INSTANCE_ID, old_events, new_events)
    actions = result.actions
    # Should schedule a retry timer, not fail immediately
    assert len(actions) == 1
    assert actions[0].HasField("createTimer")
    assert actions[0].id == 2

    # Simulate the timer firing and activity being rescheduled
    expected_fire_at = current_timestamp + timedelta(seconds=1)
    old_events = old_events + new_events
    current_timestamp = expected_fire_at
    new_events = [
        helpers.new_orchestrator_started_event(current_timestamp),
        helpers.new_timer_created_event(2, current_timestamp),
        helpers.new_timer_fired_event(2, current_timestamp),
    ]
    executor = worker._OrchestrationExecutor(registry, TEST_LOGGER)
    result = executor.execute(TEST_INSTANCE_ID, old_events, new_events)
    actions = result.actions
    assert len(actions) == 1  # rescheduled task only (timer consumed)
    assert actions[0].HasField("scheduleTask")
    assert actions[0].id == 3  # New sequence number for retry

    # Second attempt also fails
    old_events = old_events + new_events
    new_events = [
        helpers.new_orchestrator_started_event(current_timestamp),
        helpers.new_task_scheduled_event(3, task.get_name(dummy_activity)),
        helpers.new_task_failed_event(3, Exception("generic error")),
    ]

    executor = worker._OrchestrationExecutor(registry, TEST_LOGGER)
    result = executor.execute(TEST_INSTANCE_ID, old_events, new_events)
    actions = result.actions
    # Should schedule another retry timer
    assert len(actions) == 1
    assert actions[0].HasField("createTimer")
    assert actions[0].id == 4

    # Simulate the timer firing and activity being rescheduled
    expected_fire_at = current_timestamp + timedelta(seconds=1)
    old_events = old_events + new_events
    current_timestamp = expected_fire_at
    new_events = [
        helpers.new_orchestrator_started_event(current_timestamp),
        helpers.new_timer_created_event(4, current_timestamp),
        helpers.new_timer_fired_event(4, current_timestamp),
    ]
    executor = worker._OrchestrationExecutor(registry, TEST_LOGGER)
    result = executor.execute(TEST_INSTANCE_ID, old_events, new_events)
    actions = result.actions
    assert len(actions) == 1  # rescheduled task only (timer consumed)
    assert actions[0].HasField("scheduleTask")
    assert actions[0].id == 5  # New sequence number for retry

    # Third attempt fails - should exhaust retries
    old_events = old_events + new_events
    new_events = [
        helpers.new_orchestrator_started_event(current_timestamp),
        helpers.new_task_scheduled_event(5, task.get_name(dummy_activity)),
        helpers.new_task_failed_event(5, Exception("generic error")),
    ]

    executor = worker._OrchestrationExecutor(registry, TEST_LOGGER)
    result = executor.execute(TEST_INSTANCE_ID, old_events, new_events)
    actions = result.actions
    # Now should fail - no more retries
    complete_action = get_and_validate_single_complete_orchestration_action(actions)
    assert complete_action.orchestrationStatus == pb.ORCHESTRATION_STATUS_FAILED
    assert complete_action.failureDetails.errorMessage.__contains__(
        "Activity task #5 failed: generic error"
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
        helpers.new_orchestrator_started_event(timestamp=current_timestamp),
        helpers.new_execution_started_event(parent_name, TEST_INSTANCE_ID, encoded_input=None),
        helpers.new_sub_orchestration_created_event(1, child_name, "sub-1", encoded_input=None),
    ]
    new_events = [
        helpers.new_orchestrator_started_event(timestamp=current_timestamp),
        helpers.new_sub_orchestration_failed_event(1, task.NonRetryableError("boom")),
    ]

    executor = worker._OrchestrationExecutor(registry, TEST_LOGGER)
    result = executor.execute(TEST_INSTANCE_ID, old_events, new_events)
    actions = result.actions
    complete_action = get_and_validate_single_complete_orchestration_action(actions)
    assert complete_action.orchestrationStatus == pb.ORCHESTRATION_STATUS_FAILED
    assert complete_action.failureDetails.errorMessage.__contains__(
        "Sub-orchestration task #1 failed: boom"
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
        helpers.new_orchestrator_started_event(timestamp=current_timestamp),
        helpers.new_execution_started_event(parent_name, TEST_INSTANCE_ID, encoded_input=None),
        helpers.new_sub_orchestration_created_event(1, child_name, "sub-1", encoded_input=None),
    ]
    new_events = [
        helpers.new_orchestrator_started_event(timestamp=current_timestamp),
        helpers.new_sub_orchestration_failed_event(1, ValueError("boom")),
    ]

    executor = worker._OrchestrationExecutor(registry, TEST_LOGGER)
    result = executor.execute(TEST_INSTANCE_ID, old_events, new_events)
    actions = result.actions
    complete_action = get_and_validate_single_complete_orchestration_action(actions)
    assert complete_action.orchestrationStatus == pb.ORCHESTRATION_STATUS_FAILED
    assert complete_action.failureDetails.errorMessage.__contains__(
        "Sub-orchestration task #1 failed: boom"
    )


def get_and_validate_single_complete_orchestration_action(
    actions: list[pb.OrchestratorAction],
) -> pb.CompleteOrchestrationAction:
    assert len(actions) == 1
    assert type(actions[0]) is pb.OrchestratorAction
    assert actions[0].HasField("completeOrchestration")
    return actions[0].completeOrchestration
