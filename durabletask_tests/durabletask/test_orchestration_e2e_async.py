# Copyright (c) The Dapr Authors.
# Licensed under the MIT License.

import asyncio
import json
import threading
from datetime import timedelta

import pytest

from durabletask import task, worker
from durabletask.aio.client import AsyncTaskHubGrpcClient
from durabletask.client import OrchestrationStatus

# NOTE: These tests assume a sidecar process is running. Example command:
#       go install github.com/dapr/durabletask-go@main
#       durabletask-go --port 4001
pytestmark = [pytest.mark.e2e, pytest.mark.asyncio]


async def test_empty_orchestration():
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

        c = AsyncTaskHubGrpcClient(channel_options=channel_options)
        id = await c.schedule_new_orchestration(empty_orchestrator)
        state = await c.wait_for_orchestration_completion(id, timeout=30)
        await c.aclose()

    assert invoked
    assert state is not None
    assert state.name == task.get_name(empty_orchestrator)
    assert state.instance_id == id
    assert state.failure_details is None
    assert state.runtime_status == OrchestrationStatus.COMPLETED
    assert state.serialized_input is None
    assert state.serialized_output is None
    assert state.serialized_custom_status is None


async def test_activity_sequence():
    def plus_one(_: task.ActivityContext, input: int) -> int:
        return input + 1

    def sequence(ctx: task.OrchestrationContext, start_val: int):
        numbers = [start_val]
        current = start_val
        for _ in range(10):
            current = yield ctx.call_activity(plus_one, input=current)
            numbers.append(current)
        return numbers

    channel_options = [
        ("grpc.max_send_message_length", 1024 * 1024),  # 1MB
    ]
    # Start a worker, which will connect to the sidecar in a background thread
    with worker.TaskHubGrpcWorker(channel_options=channel_options) as w:
        w.add_orchestrator(sequence)
        w.add_activity(plus_one)
        w.start()

        client = AsyncTaskHubGrpcClient(channel_options=channel_options)
        id = await client.schedule_new_orchestration(sequence, input=1)
        state = await client.wait_for_orchestration_completion(id, timeout=30)
        await client.aclose()

    assert state is not None
    assert state.name == task.get_name(sequence)
    assert state.instance_id == id
    assert state.runtime_status == OrchestrationStatus.COMPLETED
    assert state.failure_details is None
    assert state.serialized_input == json.dumps(1)
    assert state.serialized_output == json.dumps([1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11])
    assert state.serialized_custom_status is None


async def test_activity_error_handling():
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

        client = AsyncTaskHubGrpcClient()
        id = await client.schedule_new_orchestration(orchestrator, input=1)
        state = await client.wait_for_orchestration_completion(id, timeout=30)
        await client.aclose()

    assert state is not None
    assert state.name == task.get_name(orchestrator)
    assert state.instance_id == id
    assert state.runtime_status == OrchestrationStatus.COMPLETED
    assert state.serialized_output == json.dumps("Kah-BOOOOM!!!")
    assert state.failure_details is None
    assert state.serialized_custom_status is None
    assert compensation_counter == 2


async def test_sub_orchestration_fan_out():
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

        client = AsyncTaskHubGrpcClient()
        id = await client.schedule_new_orchestration(parent_orchestrator, input=10)
        state = await client.wait_for_orchestration_completion(id, timeout=30)
        await client.aclose()

    assert state is not None
    assert state.runtime_status == OrchestrationStatus.COMPLETED
    assert state.failure_details is None
    assert activity_counter == 30


async def test_wait_for_multiple_external_events():
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
        client = AsyncTaskHubGrpcClient()
        id = await client.schedule_new_orchestration(orchestrator)
        await client.raise_orchestration_event(id, "A", data="a")
        await client.raise_orchestration_event(id, "B", data="b")
        await client.raise_orchestration_event(id, "C", data="c")
        state = await client.wait_for_orchestration_completion(id, timeout=30)
        await client.aclose()

    assert state is not None
    assert state.runtime_status == OrchestrationStatus.COMPLETED
    assert state.serialized_output == json.dumps(["a", "b", "c"])


@pytest.mark.parametrize("raise_event", [True, False])
async def test_wait_for_external_event_timeout(raise_event: bool):
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
        client = AsyncTaskHubGrpcClient()
        id = await client.schedule_new_orchestration(orchestrator)
        if raise_event:
            await client.raise_orchestration_event(id, "Approval")
        state = await client.wait_for_orchestration_completion(id, timeout=30)
        await client.aclose()

    assert state is not None
    assert state.runtime_status == OrchestrationStatus.COMPLETED
    if raise_event:
        assert state.serialized_output == json.dumps("approved")
    else:
        assert state.serialized_output == json.dumps("timed out")


async def test_suspend_and_resume():
    def orchestrator(ctx: task.OrchestrationContext, _):
        result = yield ctx.wait_for_external_event("my_event")
        return result

    # Start a worker, which will connect to the sidecar in a background thread
    with worker.TaskHubGrpcWorker(stop_timeout=2.0) as w:
        w.add_orchestrator(orchestrator)
        w.start()
        # there could be a race condition if the workflow is scheduled before orchestrator is started
        await asyncio.sleep(0.2)

        async with AsyncTaskHubGrpcClient() as client:
            id = await client.schedule_new_orchestration(orchestrator)
            state = await client.wait_for_orchestration_start(id, timeout=30)
            assert state is not None

            # Suspend the orchestration and wait for it to go into the SUSPENDED state
            await client.suspend_orchestration(id)
            while state.runtime_status == OrchestrationStatus.RUNNING:
                await asyncio.sleep(0.1)
                state = await client.get_orchestration_state(id)
                assert state is not None
            assert state.runtime_status == OrchestrationStatus.SUSPENDED

            # Raise an event to the orchestration and confirm that it does NOT complete
            await client.raise_orchestration_event(id, "my_event", data=42)
            try:
                state = await client.wait_for_orchestration_completion(id, timeout=3)
                assert False, "Orchestration should not have completed"
            except TimeoutError:
                pass

            # Resume the orchestration and wait for it to complete
            await client.resume_orchestration(id)
            state = await client.wait_for_orchestration_completion(id, timeout=30)
            assert state is not None
            assert state.runtime_status == OrchestrationStatus.COMPLETED
            assert state.serialized_output == json.dumps(42)


async def test_terminate():
    def orchestrator(ctx: task.OrchestrationContext, _):
        result = yield ctx.wait_for_external_event("my_event")
        return result

    # Start a worker, which will connect to the sidecar in a background thread
    with worker.TaskHubGrpcWorker(stop_timeout=2.0) as w:
        w.add_orchestrator(orchestrator)
        w.start()

        async with AsyncTaskHubGrpcClient() as client:
            id = await client.schedule_new_orchestration(orchestrator)
            state = await client.wait_for_orchestration_start(id, timeout=30)
            assert state is not None
            assert state.runtime_status == OrchestrationStatus.RUNNING

            await client.terminate_orchestration(id, output="some reason for termination")
            state = await client.wait_for_orchestration_completion(id, timeout=30)
            assert state is not None
            assert state.runtime_status == OrchestrationStatus.TERMINATED
            assert state.serialized_output == json.dumps("some reason for termination")


async def test_terminate_recursive():
    def root(ctx: task.OrchestrationContext, _):
        result = yield ctx.call_sub_orchestrator(child)
        return result

    def child(ctx: task.OrchestrationContext, _):
        result = yield ctx.wait_for_external_event("my_event")
        return result

    # Start a worker, which will connect to the sidecar in a background thread
    with worker.TaskHubGrpcWorker(stop_timeout=2.0) as w:
        w.add_orchestrator(root)
        w.add_orchestrator(child)
        w.start()

        async with AsyncTaskHubGrpcClient() as client:
            id = await client.schedule_new_orchestration(root)
            state = await client.wait_for_orchestration_start(id, timeout=30)
            assert state is not None
            assert state.runtime_status == OrchestrationStatus.RUNNING

            # Terminate root orchestration(recursive set to True by default)
            await client.terminate_orchestration(id, output="some reason for termination")
            state = await client.wait_for_orchestration_completion(id, timeout=30)
            assert state is not None
            assert state.runtime_status == OrchestrationStatus.TERMINATED

            # Verify that child orchestration is also terminated
            await client.wait_for_orchestration_completion(id, timeout=30)
            assert state is not None
            assert state.runtime_status == OrchestrationStatus.TERMINATED

            await client.purge_orchestration(id)
            state = await client.get_orchestration_state(id)
            assert state is None


async def test_continue_as_new():
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

        async with AsyncTaskHubGrpcClient() as client:
            id = await client.schedule_new_orchestration(orchestrator, input=0)
            await client.raise_orchestration_event(id, "my_event", data=1)
            await client.raise_orchestration_event(id, "my_event", data=2)
            await client.raise_orchestration_event(id, "my_event", data=3)
            await client.raise_orchestration_event(id, "my_event", data=4)
            await client.raise_orchestration_event(id, "my_event", data=5)

            state = await client.wait_for_orchestration_completion(id, timeout=30)
            assert state is not None
            assert state.runtime_status == OrchestrationStatus.COMPLETED
            assert state.serialized_output == json.dumps(all_results)
            assert state.serialized_input == json.dumps(4)
            assert all_results == [1, 2, 3, 4, 5]


async def test_retry_policies():
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

        async with AsyncTaskHubGrpcClient() as client:
            id = await client.schedule_new_orchestration(parent_orchestrator_with_retry)
            state = await client.wait_for_orchestration_completion(id, timeout=30)
            assert state is not None
            assert state.runtime_status == OrchestrationStatus.FAILED
            assert state.failure_details is not None
            assert state.failure_details.error_type == "TaskFailedError"
            assert "Sub-orchestration task #" in state.failure_details.message
            assert "failed:" in state.failure_details.message
            assert state.failure_details.message.endswith("failed: Kah-BOOOOM!!!")
            assert state.failure_details.stack_trace is not None
            assert throw_activity_counter == 9
            assert child_orch_counter == 3


async def test_retry_timeout():
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

        async with AsyncTaskHubGrpcClient() as client:
            id = await client.schedule_new_orchestration(mock_orchestrator)
            state = await client.wait_for_orchestration_completion(id, timeout=30)
            assert state is not None
            assert state.runtime_status == OrchestrationStatus.FAILED
            assert state.failure_details is not None
            assert state.failure_details.error_type == "TaskFailedError"
            assert state.failure_details.message.endswith("failed: Kah-BOOOOM!!!")
            assert state.failure_details.stack_trace is not None
            assert throw_activity_counter == 4


async def test_custom_status():
    def empty_orchestrator(ctx: task.OrchestrationContext, _):
        ctx.set_custom_status("foobaz")

    # Start a worker, which will connect to the sidecar in a background thread
    with worker.TaskHubGrpcWorker(stop_timeout=2.0) as w:
        w.add_orchestrator(empty_orchestrator)
        w.start()

        async with AsyncTaskHubGrpcClient() as client:
            id = await client.schedule_new_orchestration(empty_orchestrator)
            state = await client.wait_for_orchestration_completion(id, timeout=30)

    assert state is not None
    assert state.name == task.get_name(empty_orchestrator)
    assert state.instance_id == id
    assert state.failure_details is None
    assert state.runtime_status == OrchestrationStatus.COMPLETED
    assert state.serialized_input is None
    assert state.serialized_output is None
    assert state.serialized_custom_status == "foobaz"
