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

from datetime import datetime, timedelta

import pytest

from dapr.ext.workflow import RetryPolicy
from dapr.ext.workflow._durabletask import task


def test_retry_policy_positive_attempts():
    policy = RetryPolicy(
        first_retry_interval=timedelta(seconds=1),
        max_number_of_attempts=5,
        backoff_coefficient=2.0,
        max_retry_interval=timedelta(seconds=30),
        retry_timeout=timedelta(minutes=5),
    )
    assert policy.max_number_of_attempts == 5
    assert policy.first_retry_interval == timedelta(seconds=1)
    assert policy.backoff_coefficient == 2.0
    assert policy.max_retry_interval == timedelta(seconds=30)
    assert policy.retry_timeout == timedelta(minutes=5)


def test_retry_policy_infinite_attempts_allowed():
    policy = RetryPolicy(
        first_retry_interval=timedelta(seconds=2),
        max_number_of_attempts=-1,
    )
    assert policy.max_number_of_attempts == -1
    assert policy.obj.max_number_of_attempts == -1


def test_task_retry_policy_infinite_attempts_allowed():
    policy = task.RetryPolicy(
        first_retry_interval=timedelta(seconds=2),
        max_number_of_attempts=-1,
    )
    assert policy.max_number_of_attempts == -1


@pytest.mark.parametrize('invalid_attempts', [0, -2, -10])
def test_retry_policy_invalid_attempts_raise(invalid_attempts):
    with pytest.raises(ValueError, match='max_number_of_attempts must be >= 1 or -1'):
        RetryPolicy(
            first_retry_interval=timedelta(seconds=1),
            max_number_of_attempts=invalid_attempts,
        )

    with pytest.raises(ValueError, match='max_number_of_attempts must be >= 1 or -1'):
        task.RetryPolicy(
            first_retry_interval=timedelta(seconds=1),
            max_number_of_attempts=invalid_attempts,
        )


def test_compute_next_delay_stops_at_bounded_attempts():
    policy = task.RetryPolicy(
        first_retry_interval=timedelta(seconds=1),
        max_number_of_attempts=3,
    )
    retryable: task.RetryableTask[object] = task.RetryableTask(
        retry_policy=policy,
        start_time=datetime.now(),
        is_sub_orch=False,
        task_name='dummy',
        encoded_input=None,
        task_execution_id='1',
    )

    # Attempt 1: delay computed for attempt 2
    delay1 = retryable.compute_next_delay()
    assert delay1 == timedelta(seconds=1)

    # Attempt 2: delay computed for attempt 3
    retryable.increment_attempt_count()
    delay2 = retryable.compute_next_delay()
    assert delay2 == timedelta(seconds=1)

    # Attempt 3: reached max_number_of_attempts (3), no more retries
    retryable.increment_attempt_count()
    assert retryable.compute_next_delay() is None


def test_compute_next_delay_infinite_retries():
    policy = task.RetryPolicy(
        first_retry_interval=timedelta(seconds=1),
        max_number_of_attempts=-1,
        backoff_coefficient=1.0,
    )
    retryable: task.RetryableTask[object] = task.RetryableTask(
        retry_policy=policy,
        start_time=datetime.now(),
        is_sub_orch=False,
        task_name='dummy',
        encoded_input=None,
        task_execution_id='1',
    )

    # Verify that it continues returning delay across many attempts without stopping
    for attempt in range(1, 50):
        delay = retryable.compute_next_delay()
        assert delay == timedelta(seconds=1), f'Failed on attempt {attempt}'
        retryable.increment_attempt_count()


def test_compute_next_delay_infinite_retry_respects_timeout():
    policy = task.RetryPolicy(
        first_retry_interval=timedelta(seconds=2),
        max_number_of_attempts=-1,
        retry_timeout=timedelta(seconds=5),
    )
    retryable: task.RetryableTask[object] = task.RetryableTask(
        retry_policy=policy,
        start_time=datetime.now(),
        is_sub_orch=False,
        task_name='dummy',
        encoded_input=None,
        task_execution_id='1',
    )

    # Attempt 1 (elapsed 2s <= 5s)
    assert retryable.compute_next_delay() == timedelta(seconds=2)
    retryable.increment_attempt_count()

    # Attempt 2 (elapsed 4s <= 5s)
    assert retryable.compute_next_delay() == timedelta(seconds=2)
    retryable.increment_attempt_count()

    # Attempt 3 (elapsed 6s > 5s timeout) -> should return None
    assert retryable.compute_next_delay() is None


def test_compute_next_delay_infinite_retry_exponential_backoff_large_attempts():
    policy = task.RetryPolicy(
        first_retry_interval=timedelta(seconds=1),
        max_number_of_attempts=-1,
        backoff_coefficient=2.0,
    )
    start = datetime(2026, 1, 1, 0, 0, 0)
    retryable: task.RetryableTask[object] = task.RetryableTask(
        retry_policy=policy,
        start_time=start,
        is_sub_orch=False,
        task_name='dummy',
        encoded_input=None,
        task_execution_id='1',
    )

    # Attempt 100 exceeds standard timedelta seconds bounds without max_retry_interval
    retryable._attempt_count = 100
    delay100 = retryable.compute_next_delay()
    assert delay100 is not None
    # Verify the delay can be safely added to worker.current_utc_datetime without OverflowError
    current_utc = start + timedelta(hours=1)
    fire_at = current_utc + delay100
    assert fire_at <= datetime.max

    # Attempt 1100 triggers math.pow OverflowError, capped at the same safe datetime limit
    retryable._attempt_count = 1100
    delay1100 = retryable.compute_next_delay()
    assert delay1100 == delay100
    fire_at_1100 = current_utc + delay1100
    assert fire_at_1100 <= datetime.max


def test_compute_next_delay_infinite_retry_loop_break_optimization():
    policy = task.RetryPolicy(
        first_retry_interval=timedelta(seconds=1),
        max_number_of_attempts=-1,
        backoff_coefficient=2.0,
        max_retry_interval=timedelta(seconds=16),
        retry_timeout=timedelta(seconds=100),
    )
    retryable: task.RetryableTask[object] = task.RetryableTask(
        retry_policy=policy,
        start_time=datetime.now(),
        is_sub_orch=False,
        task_name='dummy',
        encoded_input=None,
        task_execution_id='1',
    )

    # At attempt 5: intervals are 1, 2, 4, 8, 16. Total elapsed = 31s. Next delay = 16s.
    retryable._attempt_count = 5
    assert retryable.compute_next_delay() == timedelta(seconds=16)

    # At attempt 9: intervals are 1, 2, 4, 8, 16, 16, 16, 16, 16. Total = 31 + 4*16 = 95s <= 100s.
    retryable._attempt_count = 9
    assert retryable.compute_next_delay() == timedelta(seconds=16)

    # At attempt 10: total elapsed = 95 + 16 = 111s > 100s timeout -> None
    retryable._attempt_count = 10
    assert retryable.compute_next_delay() is None
