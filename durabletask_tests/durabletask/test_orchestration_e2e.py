# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

import json
import threading
import time
from datetime import timedelta
from typing import Optional

import pytest

from durabletask import client, task, worker

# NOTE: These tests assume a sidecar process is running. Example command:
#       dapr init || true
#       dapr run --app-id test-app --dapr-grpc-port  4001
pytestmark = pytest.mark.e2e


def _wait_until_terminal(
    hub_client: client.TaskHubGrpcClient,
    instance_id: str,
    *,
    timeout_s: int = 30,
    fetch_payloads: bool = True,
) -> Optional[client.OrchestrationState]:
    """Polling-based completion wait that does not rely on the completion stream.

    Returns the terminal state or None if timeout.
    """
    deadline = time.time() + timeout_s
    delay = 0.1
    while time.time() < deadline:
        st = hub_client.get_orchestration_state(instance_id, fetch_payloads=fetch_payloads)
        if st and st.runtime_status in (
            client.OrchestrationStatus.COMPLETED,
            client.OrchestrationStatus.FAILED,
            client.OrchestrationStatus.TERMINATED,
            client.OrchestrationStatus.CANCELED,
        ):
            return st
        time.sleep(delay)
        delay = min(delay * 1.5, 1.0)
    return None


def test_empty_orchestration():
    invoked = False

    def empty_orchestrator(ctx: task.OrchestrationContext, _):
        nonlocal invoked  # don't do this in a real app!
        invoked = True

    channel_options = [
        ("grpc.max_send_message_length", 1024 * 1024),  # 1MB
    ]

    # Start a worker, which will connect to the sidecar in a background thread
    with worker.TaskHubGrpcWorker(channel_options=channel_options) as w:
        w.add_orchestrator(empty_orchestrator)
        w.start()

        # set a custom max send length option
        c = client.TaskHubGrpcClient(channel_options=channel_options)
        id = c.schedule_new_orchestration(empty_orchestrator)
        state = c.wait_for_orchestration_completion(id, timeout=30)

        # Test calling wait again on already-completed orchestration (should return immediately)
        state2 = c.wait_for_orchestration_completion(id, timeout=30)
        assert state2 is not None
        assert state2.runtime_status == client.OrchestrationStatus.COMPLETED

    assert invoked
    assert state is not None
    assert state.name == task.get_name(empty_orchestrator)
    assert state.instance_id == id
    assert state.failure_details is None
    assert state.runtime_status == client.OrchestrationStatus.COMPLETED
    assert state.serialized_input is None
    assert state.serialized_output is None
    assert state.serialized_custom_status is None


def test_activity_sequence():
    def plus_one(_: task.ActivityContext, input: int) -> int:
        return input + 1

    def sequence(ctx: task.OrchestrationContext, start_val: int):
        numbers = [start_val]
        current = start_val
        for _ in range(10):
            current = yield ctx.call_activity(plus_one, input=current)
            numbers.append(current)
        return numbers

    # Start a worker, which will connect to the sidecar in a background thread
    with worker.TaskHubGrpcWorker(stop_timeout=2.0) as w:
        w.add_orchestrator(sequence)
        w.add_activity(plus_one)
        w.start()

        with client.TaskHubGrpcClient() as task_hub_client:
            id = task_hub_client.schedule_new_orchestration(sequence, input=1)
            state = task_hub_client.wait_for_orchestration_completion(id, timeout=30)

    assert state is not None
    assert state.name == task.get_name(sequence)
    assert state.instance_id == id
    assert state.runtime_status == client.OrchestrationStatus.COMPLETED
    assert state.failure_details is None
    assert state.serialized_input == json.dumps(1)
    assert state.serialized_output == json.dumps([1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11])
    assert state.serialized_custom_status is None


def test_activity_error_handling():
    def throw(_: task.ActivityContext, input: int) -> int:
        raise RuntimeError("Kah-BOOOOM!!!")

    compensation_counter = 0

    def increment_counter(ctx, _):
        nonlocal compensation_counter
        compensation_counter += 1

    def orchestrator(ctx: task.OrchestrationContext, input: int):
        error_msg = ""
        try:
            yield ctx.call_activity(throw, input=input)
        except task.TaskFailedError as e:
            error_msg = e.details.message

            # compensating actions
            yield ctx.call_activity(increment_counter)
            yield ctx.call_activity(increment_counter)

        return error_msg

    # Start a worker, which will connect to the sidecar in a background thread
    with worker.TaskHubGrpcWorker(stop_timeout=2.0) as w:
        w.add_orchestrator(orchestrator)
        w.add_activity(throw)
        w.add_activity(increment_counter)
        w.start()

        with client.TaskHubGrpcClient() as task_hub_client:
            id = task_hub_client.schedule_new_orchestration(orchestrator, input=1)
            state = task_hub_client.wait_for_orchestration_completion(id, timeout=30)

    assert state is not None
    assert state.name == task.get_name(orchestrator)
    assert state.instance_id == id
    assert state.runtime_status == client.OrchestrationStatus.COMPLETED
    assert state.serialized_output == json.dumps("Kah-BOOOOM!!!")
    assert state.failure_details is None
    assert state.serialized_custom_status is None
    assert compensation_counter == 2


def test_sub_orchestration_fan_out():
    threadLock = threading.Lock()
    activity_counter = 0

    def increment(ctx, _):
        with threadLock:
            nonlocal activity_counter
            activity_counter += 1

    def orchestrator_child(ctx: task.OrchestrationContext, activity_count: int):
        for _ in range(activity_count):
            yield ctx.call_activity(increment)

    def parent_orchestrator(ctx: task.OrchestrationContext, count: int):
        # Fan out to multiple sub-orchestrations
        tasks = []
        for _ in range(count):
            tasks.append(ctx.call_sub_orchestrator(orchestrator_child, input=3))
        # Wait for all sub-orchestrations to complete
        yield task.when_all(tasks)

    # Start a worker, which will connect to the sidecar in a background thread
    with worker.TaskHubGrpcWorker(stop_timeout=2.0) as w:
        w.add_activity(increment)
        w.add_orchestrator(orchestrator_child)
        w.add_orchestrator(parent_orchestrator)
        w.start()

        with client.TaskHubGrpcClient() as task_hub_client:
            id = task_hub_client.schedule_new_orchestration(parent_orchestrator, input=10)
            state = task_hub_client.wait_for_orchestration_completion(id, timeout=30)

    assert state is not None
    assert state.runtime_status == client.OrchestrationStatus.COMPLETED
    assert state.failure_details is None
    assert activity_counter == 30


def test_wait_for_multiple_external_events():
    def orchestrator(ctx: task.OrchestrationContext, _):
        a = yield ctx.wait_for_external_event("A")
        b = yield ctx.wait_for_external_event("B")
        c = yield ctx.wait_for_external_event("C")
        return [a, b, c]

    # Start a worker, which will connect to the sidecar in a background thread
    with worker.TaskHubGrpcWorker(stop_timeout=2.0) as w:
        w.add_orchestrator(orchestrator)
        w.start()

        # Start the orchestration and immediately raise events to it.
        task_hub_client = client.TaskHubGrpcClient()
        id = task_hub_client.schedule_new_orchestration(orchestrator)
        task_hub_client.raise_orchestration_event(id, "A", data="a")
        task_hub_client.raise_orchestration_event(id, "B", data="b")
        task_hub_client.raise_orchestration_event(id, "C", data="c")
        state = task_hub_client.wait_for_orchestration_completion(id, timeout=30)

    assert state is not None
    assert state.runtime_status == client.OrchestrationStatus.COMPLETED
    assert state.serialized_output == json.dumps(["a", "b", "c"])


@pytest.mark.parametrize("raise_event", [True, False])
def test_wait_for_external_event_timeout(raise_event: bool):
    def orchestrator(ctx: task.OrchestrationContext, _):
        approval: task.Task[bool] = ctx.wait_for_external_event("Approval")
        timeout = ctx.create_timer(timedelta(seconds=3))
        winner = yield task.when_any([approval, timeout])
        if winner == approval:
            return "approved"
        else:
            return "timed out"

    # Start a worker, which will connect to the sidecar in a background thread
    with worker.TaskHubGrpcWorker(stop_timeout=2.0) as w:
        w.add_orchestrator(orchestrator)
        w.start()

        # Start the orchestration and immediately raise events to it.
        with client.TaskHubGrpcClient() as task_hub_client:
            id = task_hub_client.schedule_new_orchestration(orchestrator)
            if raise_event:
                task_hub_client.raise_orchestration_event(id, "Approval")
            state = task_hub_client.wait_for_orchestration_completion(id, timeout=30)

    assert state is not None
    assert state.runtime_status == client.OrchestrationStatus.COMPLETED
    if raise_event:
        assert state.serialized_output == json.dumps("approved")
    else:
        assert state.serialized_output == json.dumps("timed out")


def test_suspend_and_resume():
    def orchestrator(ctx: task.OrchestrationContext, _):
        result = yield ctx.wait_for_external_event("my_event")
        return result

    # Start a worker, which will connect to the sidecar in a background thread
    with worker.TaskHubGrpcWorker(stop_timeout=2.0) as w:
        w.add_orchestrator(orchestrator)
        w.start()

        with client.TaskHubGrpcClient() as task_hub_client:
            id = task_hub_client.schedule_new_orchestration(orchestrator)
            state = task_hub_client.wait_for_orchestration_start(id, timeout=30)
            assert state is not None

            # Suspend the orchestration and wait for it to go into the SUSPENDED state
            task_hub_client.suspend_orchestration(id)
            while state.runtime_status == client.OrchestrationStatus.RUNNING:
                time.sleep(0.1)
                state = task_hub_client.get_orchestration_state(id)
                assert state is not None
            assert state.runtime_status == client.OrchestrationStatus.SUSPENDED

            # Raise an event to the orchestration and confirm that it does NOT complete
            task_hub_client.raise_orchestration_event(id, "my_event", data=42)
            try:
                state = task_hub_client.wait_for_orchestration_completion(id, timeout=3)
                assert False, "Orchestration should not have completed"
            except TimeoutError:
                pass

            # Resume the orchestration and wait for it to complete
            task_hub_client.resume_orchestration(id)
            state = task_hub_client.wait_for_orchestration_completion(id, timeout=30)
            assert state is not None
            assert state.runtime_status == client.OrchestrationStatus.COMPLETED
            assert state.serialized_output == json.dumps(42)


def test_terminate():
    def orchestrator(ctx: task.OrchestrationContext, _):
        result = yield ctx.wait_for_external_event("my_event")
        return result

    # Start a worker, which will connect to the sidecar in a background thread
    with worker.TaskHubGrpcWorker(stop_timeout=2.0) as w:
        w.add_orchestrator(orchestrator)
        w.start()

        with client.TaskHubGrpcClient() as task_hub_client:
            id = task_hub_client.schedule_new_orchestration(orchestrator)
            state = task_hub_client.wait_for_orchestration_start(id, timeout=30)
            assert state is not None
            assert state.runtime_status == client.OrchestrationStatus.RUNNING

            task_hub_client.terminate_orchestration(id, output="some reason for termination")
            state = task_hub_client.wait_for_orchestration_completion(id, timeout=30)
            assert state is not None
            assert state.runtime_status == client.OrchestrationStatus.TERMINATED
            assert state.serialized_output == json.dumps("some reason for termination")


def test_terminate_recursive():
    thread_lock = threading.Lock()
    activity_counter = 0
    delay_time = (
        2  # seconds (already optimized from 4s - don't reduce further as it can leads to failure)
    )

    def increment(ctx, _):
        with thread_lock:
            nonlocal activity_counter
            activity_counter += 1
        raise Exception("Failed: Should not have executed the activity")

    def orchestrator_child(ctx: task.OrchestrationContext, activity_count: int):
        due_time = ctx.current_utc_datetime + timedelta(seconds=delay_time)
        yield ctx.create_timer(due_time)
        yield ctx.call_activity(increment)

    def parent_orchestrator(ctx: task.OrchestrationContext, count: int):
        tasks = []
        for _ in range(count):
            tasks.append(ctx.call_sub_orchestrator(orchestrator_child, input=count))
        yield task.when_all(tasks)

    for recurse in [True, False]:
        with worker.TaskHubGrpcWorker(stop_timeout=2.0) as w:
            w.add_activity(increment)
            w.add_orchestrator(orchestrator_child)
            w.add_orchestrator(parent_orchestrator)
            w.start()

            with client.TaskHubGrpcClient() as task_hub_client:
                instance_id = task_hub_client.schedule_new_orchestration(
                    parent_orchestrator, input=5
                )

                time.sleep(1)  # Brief delay to let orchestrations start

                output = "Recursive termination = {recurse}"
                task_hub_client.terminate_orchestration(
                    instance_id, output=output, recursive=recurse
                )

                metadata = task_hub_client.wait_for_orchestration_completion(
                    instance_id, timeout=30
                )
                assert metadata is not None
                assert metadata.runtime_status == client.OrchestrationStatus.TERMINATED
                assert metadata.serialized_output == f'"{output}"'
                time.sleep(delay_time)  # Wait for timer to check activity execution
                if recurse:
                    assert activity_counter == 0, (
                        "Activity should not have executed with recursive termination"
                    )
                else:
                    assert activity_counter == 5, (
                        "Activity should have executed without recursive termination"
                    )


def test_continue_as_new():
    all_results = []

    def orchestrator(ctx: task.OrchestrationContext, input: int):
        result = yield ctx.wait_for_external_event("my_event")
        if not ctx.is_replaying:
            # NOTE: Real orchestrations should never interact with nonlocal variables like this.
            nonlocal all_results  # noqa: F824
            all_results.append(result)

        if len(all_results) <= 4:
            ctx.continue_as_new(max(all_results), save_events=True)
        else:
            return all_results

    # Start a worker, which will connect to the sidecar in a background thread
    with worker.TaskHubGrpcWorker(stop_timeout=2.0) as w:
        w.add_orchestrator(orchestrator)
        w.start()

        task_hub_client = client.TaskHubGrpcClient()
        id = task_hub_client.schedule_new_orchestration(orchestrator, input=0)
        task_hub_client.raise_orchestration_event(id, "my_event", data=1)
        task_hub_client.raise_orchestration_event(id, "my_event", data=2)
        task_hub_client.raise_orchestration_event(id, "my_event", data=3)
        task_hub_client.raise_orchestration_event(id, "my_event", data=4)
        task_hub_client.raise_orchestration_event(id, "my_event", data=5)

        state = task_hub_client.wait_for_orchestration_completion(id, timeout=30)
        assert state is not None
        assert state.runtime_status == client.OrchestrationStatus.COMPLETED
        assert state.serialized_output == json.dumps(all_results)
        assert state.serialized_input == json.dumps(4)
        assert all_results == [1, 2, 3, 4, 5]


def test_continue_as_new_with_activity_e2e():
    """E2E test for continue_as_new with activities (generator-based)."""
    activity_results = []

    def double_activity(ctx: task.ActivityContext, value: int) -> int:
        """Activity that doubles the value."""
        result = value * 2
        activity_results.append(result)
        return result

    def orchestrator(ctx: task.OrchestrationContext, counter: int):
        # Call activity to process the counter
        processed = yield ctx.call_activity(double_activity, input=counter)

        # Continue as new up to 3 times
        if counter < 3:
            ctx.continue_as_new(counter + 1, save_events=False)
        else:
            return {"counter": counter, "processed": processed, "all_results": activity_results}

    with worker.TaskHubGrpcWorker(stop_timeout=2.0) as w:
        w.add_activity(double_activity)
        w.add_orchestrator(orchestrator)
        w.start()

        task_hub_client = client.TaskHubGrpcClient()
        id = task_hub_client.schedule_new_orchestration(orchestrator, input=1)

        state = task_hub_client.wait_for_orchestration_completion(id, timeout=30)
        assert state is not None
        assert state.runtime_status == client.OrchestrationStatus.COMPLETED

        output = json.loads(state.serialized_output)
        # Should have called activity 3 times with input values 1, 2, 3
        assert activity_results == [2, 4, 6]
        assert output["counter"] == 3
        assert output["processed"] == 6


# NOTE: This test fails when running against durabletask-go with sqlite because the sqlite backend does not yet
#       support orchestration ID reuse. This gap is being tracked here:
#       https://github.com/microsoft/durabletask-go/issues/42
def test_retry_policies():
    # This test verifies that the retry policies are working as expected.
    # It does this by creating an orchestration that calls a sub-orchestrator,
    # which in turn calls an activity that always fails.
    # In this test, the retry policies are added, and the orchestration
    # should still fail. But, number of times the sub-orchestrator and activity
    # is called should increase as per the retry policies.

    child_orch_counter = 0
    throw_activity_counter = 0

    # Second setup: With retry policies (minimal delays for faster tests)
    retry_policy = task.RetryPolicy(
        first_retry_interval=timedelta(seconds=0.05),  # 0.1 → 0.05 (50% faster)
        max_number_of_attempts=3,
        backoff_coefficient=1,
        max_retry_interval=timedelta(seconds=0.5),  # 1 → 0.5
        retry_timeout=timedelta(seconds=2),  # 3 → 2
    )

    def parent_orchestrator_with_retry(ctx: task.OrchestrationContext, _):
        yield ctx.call_sub_orchestrator(child_orchestrator_with_retry, retry_policy=retry_policy)

    def child_orchestrator_with_retry(ctx: task.OrchestrationContext, _):
        nonlocal child_orch_counter
        if not ctx.is_replaying:
            # NOTE: Real orchestrations should never interact with nonlocal variables like this.
            # This is done only for testing purposes.
            child_orch_counter += 1
        yield ctx.call_activity(throw_activity_with_retry, retry_policy=retry_policy)

    def throw_activity_with_retry(ctx: task.ActivityContext, _):
        nonlocal throw_activity_counter
        throw_activity_counter += 1
        raise RuntimeError("Kah-BOOOOM!!!")

    with worker.TaskHubGrpcWorker(stop_timeout=2.0) as w:
        w.add_orchestrator(parent_orchestrator_with_retry)
        w.add_orchestrator(child_orchestrator_with_retry)
        w.add_activity(throw_activity_with_retry)
        w.start()

        task_hub_client = client.TaskHubGrpcClient()
        id = task_hub_client.schedule_new_orchestration(parent_orchestrator_with_retry)
        state = task_hub_client.wait_for_orchestration_completion(id, timeout=30)
        assert state is not None
        assert state.runtime_status == client.OrchestrationStatus.FAILED
        assert state.failure_details is not None
        assert state.failure_details.error_type == "TaskFailedError"
        assert "Sub-orchestration task #" in state.failure_details.message
        assert "failed:" in state.failure_details.message
        assert state.failure_details.message.endswith("failed: Kah-BOOOOM!!!")
        assert state.failure_details.stack_trace is not None
        assert throw_activity_counter == 9
        assert child_orch_counter == 3

    # Test 2: Verify NonRetryableError prevents retries even with retry policy
    non_retryable_counter = 0

    def throw_non_retryable(ctx: task.ActivityContext, _):
        nonlocal non_retryable_counter
        non_retryable_counter += 1
        raise task.NonRetryableError("Cannot retry this!")

    def orchestrator_with_non_retryable(ctx: task.OrchestrationContext, _):
        # Even with retry policy, NonRetryableError should fail immediately
        yield ctx.call_activity(throw_non_retryable, retry_policy=retry_policy)

    with worker.TaskHubGrpcWorker(stop_timeout=2.0) as w:
        w.add_orchestrator(orchestrator_with_non_retryable)
        w.add_activity(throw_non_retryable)
        w.start()

        task_hub_client = client.TaskHubGrpcClient()
        id = task_hub_client.schedule_new_orchestration(orchestrator_with_non_retryable)
        state = task_hub_client.wait_for_orchestration_completion(id, timeout=30)
        assert state is not None
        assert state.runtime_status == client.OrchestrationStatus.FAILED
        assert state.failure_details is not None
        assert "Cannot retry this!" in state.failure_details.message
        # Key assertion: activity was called exactly once (no retries)
        assert non_retryable_counter == 1


def test_retry_timeout():
    # This test verifies that the retry timeout is working as expected.
    # Max number of attempts is 5 and retry timeout is 1.7 seconds.
    # Delays: 0.25 + 0.5 + 1.0 = 1.75 seconds cumulative before 4th attempt.
    # So, the 5th attempt (which would happen at 1.75s) should not be made.
    throw_activity_counter = 0
    retry_policy = task.RetryPolicy(
        first_retry_interval=timedelta(seconds=1),
        max_number_of_attempts=5,
        backoff_coefficient=2,
        max_retry_interval=timedelta(seconds=10),
        retry_timeout=timedelta(seconds=13),  # Set just before 4th attempt
    )

    def mock_orchestrator(ctx: task.OrchestrationContext, _):
        yield ctx.call_activity(throw_activity, retry_policy=retry_policy)

    def throw_activity(ctx: task.ActivityContext, _):
        nonlocal throw_activity_counter
        throw_activity_counter += 1
        raise RuntimeError("Kah-BOOOOM!!!")

    with worker.TaskHubGrpcWorker(stop_timeout=2.0) as w:
        w.add_orchestrator(mock_orchestrator)
        w.add_activity(throw_activity)
        w.start()

        task_hub_client = client.TaskHubGrpcClient()
        id = task_hub_client.schedule_new_orchestration(mock_orchestrator)
        state = task_hub_client.wait_for_orchestration_completion(id, timeout=30)
        assert state is not None
        assert state.runtime_status == client.OrchestrationStatus.FAILED
        assert state.failure_details is not None
        assert state.failure_details.error_type == "TaskFailedError"
        assert state.failure_details.message.endswith("failed: Kah-BOOOOM!!!")
        assert state.failure_details.stack_trace is not None
        assert throw_activity_counter == 4


def test_custom_status():
    def empty_orchestrator(ctx: task.OrchestrationContext, _):
        ctx.set_custom_status("foobaz")

    # Start a worker, which will connect to the sidecar in a background thread
    with worker.TaskHubGrpcWorker(stop_timeout=2.0) as w:
        w.add_orchestrator(empty_orchestrator)
        w.start()

        c = client.TaskHubGrpcClient()
        id = c.schedule_new_orchestration(empty_orchestrator)
        state = c.wait_for_orchestration_completion(id, timeout=30)

    assert state is not None
    assert state.name == task.get_name(empty_orchestrator)
    assert state.instance_id == id
    assert state.failure_details is None
    assert state.runtime_status == client.OrchestrationStatus.COMPLETED
    assert state.serialized_input is None
    assert state.serialized_output is None
    assert state.serialized_custom_status == 'foobaz'


def test_now_with_sequence_ordering():
    """
    Test that now_with_sequence() maintains strict ordering across workflow execution.

    This verifies:
    1. Timestamps increment sequentially
    2. Order is preserved across activity calls
    3. Deterministic behavior (timestamps are consistent on replay)
    """

    def simple_activity(ctx, input_val: str):
        return f"activity_{input_val}_done"

    def timestamp_ordering_workflow(ctx: task.OrchestrationContext, _):
        timestamps = []

        # First timestamp before any activities
        t1 = ctx.now_with_sequence()
        timestamps.append(("t1_before_activities", t1.isoformat()))

        # Call first activity
        result1 = yield ctx.call_activity(simple_activity, input="first")
        timestamps.append(("activity_1_result", result1))

        # Timestamp after first activity
        t2 = ctx.now_with_sequence()
        timestamps.append(("t2_after_activity_1", t2.isoformat()))

        # Call second activity
        result2 = yield ctx.call_activity(simple_activity, input="second")
        timestamps.append(("activity_2_result", result2))

        # Timestamp after second activity
        t3 = ctx.now_with_sequence()
        timestamps.append(("t3_after_activity_2", t3.isoformat()))

        # A few more rapid timestamps to test counter incrementing
        t4 = ctx.now_with_sequence()
        timestamps.append(("t4_rapid", t4.isoformat()))

        t5 = ctx.now_with_sequence()
        timestamps.append(("t5_rapid", t5.isoformat()))

        # Return all timestamps for verification
        return {
            "timestamps": timestamps,
            "t1": t1.isoformat(),
            "t2": t2.isoformat(),
            "t3": t3.isoformat(),
            "t4": t4.isoformat(),
            "t5": t5.isoformat(),
        }

    with worker.TaskHubGrpcWorker(stop_timeout=2.0) as w:
        w.add_orchestrator(timestamp_ordering_workflow)
        w.add_activity(simple_activity)
        w.start()

        with client.TaskHubGrpcClient() as c:
            instance_id = c.schedule_new_orchestration(timestamp_ordering_workflow)
            state = c.wait_for_orchestration_completion(
                instance_id, timeout=30, fetch_payloads=True
            )

    assert state is not None
    assert state.runtime_status == client.OrchestrationStatus.COMPLETED
    assert state.failure_details is None

    # Parse result
    result = json.loads(state.serialized_output)
    assert result is not None

    # Verify all timestamps are present
    assert "t1" in result
    assert "t2" in result
    assert "t3" in result
    assert "t4" in result
    assert "t5" in result

    # Parse timestamps back to datetime objects for comparison
    from datetime import datetime

    t1 = datetime.fromisoformat(result["t1"])
    t2 = datetime.fromisoformat(result["t2"])
    t3 = datetime.fromisoformat(result["t3"])
    t4 = datetime.fromisoformat(result["t4"])
    t5 = datetime.fromisoformat(result["t5"])

    # Verify strict ordering: t1 < t2 < t3 < t4 < t5
    # This is the key guarantee - timestamps must maintain order for tracing
    assert t1 < t2, f"t1 ({t1}) should be < t2 ({t2})"
    assert t2 < t3, f"t2 ({t2}) should be < t3 ({t3})"
    assert t3 < t4, f"t3 ({t3}) should be < t4 ({t4})"
    assert t4 < t5, f"t4 ({t4}) should be < t5 ({t5})"

    # Verify that timestamps called in rapid succession (t3, t4, t5 with no activities between)
    # have exactly 1 microsecond deltas. These happen within the same replay execution.
    delta_t3_t4 = (t4 - t3).total_seconds() * 1_000_000
    delta_t4_t5 = (t5 - t4).total_seconds() * 1_000_000

    assert delta_t3_t4 == 1.0, f"t3 to t4 should be 1 microsecond, got {delta_t3_t4}"
    assert delta_t4_t5 == 1.0, f"t4 to t5 should be 1 microsecond, got {delta_t4_t5}"

    # Note: We don't check exact deltas for t1->t2 or t2->t3 because they span
    # activity calls. During replay, current_utc_datetime changes based on event
    # timestamps, so the base time shifts. However, ordering is still guaranteed.


def test_cannot_add_orchestrator_while_running():
    """Test that orchestrators cannot be added while the worker is running."""

    def orchestrator(ctx: task.OrchestrationContext, _):
        return "done"

    def another_orchestrator(ctx: task.OrchestrationContext, _):
        return "another"

    with worker.TaskHubGrpcWorker(stop_timeout=2.0) as w:
        w.add_orchestrator(orchestrator)
        w.start()

        # Try to add another orchestrator while running
        with pytest.raises(
            RuntimeError, match="Orchestrators cannot be added while the worker is running"
        ):
            w.add_orchestrator(another_orchestrator)


def test_cannot_add_activity_while_running():
    """Test that activities cannot be added while the worker is running."""

    def activity(ctx: task.ActivityContext, input):
        return input

    def another_activity(ctx: task.ActivityContext, input):
        return input * 2

    def orchestrator(ctx: task.OrchestrationContext, _):
        return "done"

    with worker.TaskHubGrpcWorker(stop_timeout=2.0) as w:
        w.add_orchestrator(orchestrator)
        w.add_activity(activity)
        w.start()

        # Try to add another activity while running
        with pytest.raises(
            RuntimeError, match="Activities cannot be added while the worker is running"
        ):
            w.add_activity(another_activity)


def test_can_add_functions_after_stop():
    """Test that orchestrators/activities can be added after stopping the worker."""

    def orchestrator1(ctx: task.OrchestrationContext, _):
        return "done"

    def orchestrator2(ctx: task.OrchestrationContext, _):
        return "done2"

    def activity(ctx: task.ActivityContext, input):
        return input

    with worker.TaskHubGrpcWorker(stop_timeout=2.0) as w:
        w.add_orchestrator(orchestrator1)
        w.start()

        c = client.TaskHubGrpcClient()
        id = c.schedule_new_orchestration(orchestrator1)
        state = c.wait_for_orchestration_completion(id, timeout=30)
        assert state is not None
        assert state.runtime_status == client.OrchestrationStatus.COMPLETED

    # Should be able to add after stop
    w.add_orchestrator(orchestrator2)
    w.add_activity(activity)
