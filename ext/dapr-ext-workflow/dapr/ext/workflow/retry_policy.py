# -*- coding: utf-8 -*-

"""
Copyright 2023 The Dapr Authors
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

from typing import Optional, TypeVar
from datetime import timedelta

from durabletask import task

T = TypeVar('T')
TInput = TypeVar('TInput')
TOutput = TypeVar('TOutput')


class RetryPolicy:
    """Represents the retry policy for a workflow or activity function."""

    def __init__(
        self,
        *,
        first_retry_interval: timedelta,
        max_number_of_attempts: int,
        backoff_coefficient: Optional[float] = 1.0,
        max_retry_interval: Optional[timedelta] = None,
        retry_timeout: Optional[timedelta] = None,
    ):
        """Creates a new RetryPolicy instance.

        Args:
            first_retry_interval(timedelta): The retry interval to use for the first retry attempt.
            max_number_of_attempts(int):  The maximum number of retry attempts.
            backoff_coefficient(Optional[float]): The backoff coefficient to use for calculating
                the next retry interval.
            max_retry_interval(Optional[timedelta]): The maximum retry interval to use for any
                retry attempt.
            retry_timeout(Optional[timedelta]): The maximum amount of time to spend retrying the
                operation.
        """
        # validate inputs
        if first_retry_interval < timedelta(seconds=0):
            raise ValueError('first_retry_interval must be >= 0')
        if max_number_of_attempts < 1:
            raise ValueError('max_number_of_attempts must be >= 1')
        if backoff_coefficient is not None and backoff_coefficient < 1:
            raise ValueError('backoff_coefficient must be >= 1')
        if max_retry_interval is not None and max_retry_interval < timedelta(seconds=0):
            raise ValueError('max_retry_interval must be >= 0')
        if retry_timeout is not None and retry_timeout < timedelta(seconds=0):
            raise ValueError('retry_timeout must be >= 0')

        self._obj = task.RetryPolicy(
            first_retry_interval=first_retry_interval,
            max_number_of_attempts=max_number_of_attempts,
            backoff_coefficient=backoff_coefficient,
            max_retry_interval=max_retry_interval,
            retry_timeout=retry_timeout,
        )

    @property
    def obj(self) -> task.RetryPolicy:
        """Returns the underlying RetryPolicy object."""
        return self._obj

    @property
    def first_retry_interval(self) -> timedelta:
        """The retry interval to use for the first retry attempt."""
        return self._obj._first_retry_interval

    @property
    def max_number_of_attempts(self) -> int:
        """The maximum number of retry attempts."""
        return self._obj._max_number_of_attempts

    @property
    def backoff_coefficient(self) -> Optional[float]:
        """The backoff coefficient to use for calculating the next retry interval."""
        return self._obj._backoff_coefficient

    @property
    def max_retry_interval(self) -> Optional[timedelta]:
        """The maximum retry interval to use for any retry attempt."""
        return self._obj._max_retry_interval

    @property
    def retry_timeout(self) -> Optional[timedelta]:
        """The maximum amount of time to spend retrying the operation."""
        return self._obj._retry_timeout
