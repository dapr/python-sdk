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

"""Unit tests for durabletask.task primitives."""

from datetime import datetime, timedelta

import dapr.ext.workflow._durabletask.internal.helpers as pbh
import pytest
from dapr.ext.workflow._durabletask import task


def _make_failure_details(message: str = 'test error', error_type: str = 'TestError'):
    """Create a TaskFailureDetails proto for testing."""
    return pbh.new_failure_details(Exception(message))


def test_when_all_empty_returns_successfully():
    """task.when_all([]) should complete immediately and return an empty list."""
    when_all_task = task.when_all([])

    assert when_all_task.is_complete
    assert when_all_task.get_result() == []


def test_when_any_empty_returns_successfully():
    """task.when_any([]) should complete immediately and return an empty list."""
    when_any_task = task.when_any([])

    assert when_any_task.is_complete
    assert when_any_task.get_result() == []


def test_when_all_happy_path_returns_ordered_results_and_completes_last():
    c1 = task.CompletableTask()
    c2 = task.CompletableTask()
    c3 = task.CompletableTask()

    all_task = task.when_all([c1, c2, c3])

    assert not all_task.is_complete

    c2.complete('two')

    assert not all_task.is_complete

    c1.complete('one')

    assert not all_task.is_complete

    c3.complete('three')

    assert all_task.is_complete

    assert all_task.get_result() == ['one', 'two', 'three']


def test_when_all_is_composable_with_when_any():
    c1 = task.CompletableTask()
    c2 = task.CompletableTask()

    any_task = task.when_any([c1, c2])
    all_task = task.when_all([any_task])

    assert not any_task.is_complete
    assert not all_task.is_complete

    c2.complete('two')

    assert any_task.is_complete
    assert all_task.is_complete
    assert all_task.get_result() == [c2]


def test_when_any_is_composable_with_when_all():
    c1 = task.CompletableTask()
    c2 = task.CompletableTask()
    c3 = task.CompletableTask()

    all_task1 = task.when_all([c1, c2])
    all_task2 = task.when_all([c3])
    any_task = task.when_any([all_task1, all_task2])

    assert not any_task.is_complete
    assert not all_task1.is_complete
    assert not all_task2.is_complete

    c1.complete('one')

    assert not any_task.is_complete
    assert not all_task1.is_complete
    assert not all_task2.is_complete

    c2.complete('two')

    assert any_task.is_complete
    assert all_task1.is_complete
    assert not all_task2.is_complete

    assert any_task.get_result() == all_task1


def test_when_any_happy_path_returns_winner_task_and_completes_on_first():
    a = task.CompletableTask()
    b = task.CompletableTask()

    any_task = task.when_any([a, b])

    assert not any_task.is_complete

    b.complete('B')

    assert any_task.is_complete

    winner = any_task.get_result()

    assert winner is b

    assert winner.get_result() == 'B'

    # Completing the other child should not change the winner
    a.complete('A')

    assert any_task.get_result() is b


def test_when_all_failure_after_success_still_reports_failure():
    """When a child fails after another child has already succeeded,
    the WhenAllTask must still complete with the failure — not swallow it."""
    c1 = task.CompletableTask()
    c2 = task.CompletableTask()

    all_task = task.when_all([c1, c2])

    # c1 succeeds first
    c1.complete('one')
    assert not all_task.is_complete

    # c2 fails second — this is the order that used to swallow the exception
    c2.fail('activity failed', _make_failure_details('activity failed'))

    assert all_task.is_complete
    assert all_task.is_failed
    with pytest.raises(task.TaskFailedError):
        all_task.get_result()


def test_when_all_failure_before_success_still_reports_failure():
    """When a child fails before the other children succeed,
    the WhenAllTask must complete with the failure immediately."""
    c1 = task.CompletableTask()
    c2 = task.CompletableTask()

    all_task = task.when_all([c1, c2])

    # c1 fails first
    c1.fail('activity failed', _make_failure_details('activity failed'))

    assert all_task.is_complete
    assert all_task.is_failed
    with pytest.raises(task.TaskFailedError):
        all_task.get_result()

    # c2 succeeds after — must not raise ValueError
    c2.complete('two')

    # WhenAllTask should still be in the same failed state
    assert all_task.is_complete
    assert all_task.is_failed
    with pytest.raises(task.TaskFailedError):
        all_task.get_result()


def test_when_all_failure_propagates_to_parent():
    """When a WhenAllTask fails due to a child failure,
    it should notify its parent composite task."""
    c1 = task.CompletableTask()
    c2 = task.CompletableTask()

    all_task = task.when_all([c1, c2])
    any_task = task.when_any([all_task])

    assert not any_task.is_complete

    c1.fail('activity failed', _make_failure_details('activity failed'))

    assert all_task.is_complete
    assert all_task.is_failed
    # The parent WhenAnyTask should also have completed
    assert any_task.is_complete
    assert any_task.get_result() is all_task


def test_retry_policy_accepts_infinite_max_attempts():
    """RetryPolicy(max_number_of_attempts=-1) is allowed and means infinite retries."""
    policy = task.RetryPolicy(first_retry_interval=timedelta(seconds=1), max_number_of_attempts=-1)
    assert policy.max_number_of_attempts == -1


@pytest.mark.parametrize('invalid', [0, -2, -5])
def test_retry_policy_rejects_invalid_max_attempts(invalid):
    """RetryPolicy rejects zero and values below -1."""
    with pytest.raises(ValueError):
        task.RetryPolicy(first_retry_interval=timedelta(seconds=1), max_number_of_attempts=invalid)


def test_retryable_task_infinite_keeps_computing_next_delay():
    """When max_number_of_attempts == -1, compute_next_delay never returns None
    due to the attempt cap (subject only to retry_timeout)."""
    policy = task.RetryPolicy(first_retry_interval=timedelta(seconds=1), max_number_of_attempts=-1)
    retryable = task.RetryableTask(
        retry_policy=policy,
        start_time=datetime.utcnow(),
        is_sub_orch=False,
        task_name='activity',
    )

    # Simulate many failed attempts; delay should continue to be produced.
    for _ in range(50):
        retryable.increment_attempt_count()
        assert retryable.compute_next_delay() is not None


def test_retryable_task_infinite_still_respects_retry_timeout():
    """When max_number_of_attempts == -1, retry_timeout must still cap the wall-clock
    window so retries do not run forever."""
    policy = task.RetryPolicy(
        first_retry_interval=timedelta(seconds=1),
        max_number_of_attempts=-1,
        retry_timeout=timedelta(seconds=3),
    )
    retryable = task.RetryableTask(
        retry_policy=policy,
        start_time=datetime.utcnow(),
        is_sub_orch=False,
        task_name='activity',
    )

    # Each attempt adds 1s of delay. First few attempts stay inside the 3s window.
    retryable.increment_attempt_count()  # attempt 2 -> cumulative delay 2s
    assert retryable.compute_next_delay() is not None
    retryable.increment_attempt_count()  # attempt 3 -> cumulative delay 3s
    # At the boundary, the logical next start == retry_expiration, which is not "<"
    assert retryable.compute_next_delay() is None


def test_retryable_task_stops_after_max_attempts():
    """With a finite cap, compute_next_delay returns None once the cap is reached."""
    policy = task.RetryPolicy(first_retry_interval=timedelta(seconds=1), max_number_of_attempts=3)
    retryable = task.RetryableTask(
        retry_policy=policy,
        start_time=datetime.utcnow(),
        is_sub_orch=False,
        task_name='activity',
    )

    # attempt 1 -> has more retries
    assert retryable.compute_next_delay() is not None
    retryable.increment_attempt_count()  # -> 2
    assert retryable.compute_next_delay() is not None
    retryable.increment_attempt_count()  # -> 3
    assert retryable.compute_next_delay() is None
