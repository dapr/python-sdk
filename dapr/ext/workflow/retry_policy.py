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

from datetime import timedelta
from typing import Optional, TypeVar

from dapr.ext.workflow._durabletask import task

T = TypeVar('T')
TInput = TypeVar('TInput')
TOutput = TypeVar('TOutput')


class RetryPolicy:
    """Represents the retry policy for a workflow or activity function."""

    def __init__(
        self,
        *,
        first_retry_interval: timedelta = timedelta(seconds=1),
        max_number_of_attempts: Optional[int] = None,
        max_attempts: Optional[int] = None,
        backoff_coefficient: Optional[float] = 1.0,
        max_retry_interval: Optional[timedelta] = timedelta(seconds=60),
        retry_timeout: Optional[timedelta] = None,
    ):
        """Creates a new RetryPolicy instance.

        Args:
            first_retry_interval(timedelta): The retry interval to use for the first retry
                attempt. Defaults to 1 second.
            max_number_of_attempts(Optional[int]): Deprecated alias for ``max_attempts``.
            max_attempts(Optional[int]): The maximum total number of attempts (including the
                initial attempt). Defaults to 1.
            backoff_coefficient(Optional[float]): The backoff coefficient to use for calculating
                the next retry interval. Defaults to 1.0.
            max_retry_interval(Optional[timedelta]): The maximum retry interval to use for any
                retry attempt. Defaults to 60 seconds.
            retry_timeout(Optional[timedelta]): The maximum amount of time to spend retrying the
                operation. Defaults to None (no overall timeout).
        """
        resolved_attempts = (
            max_attempts
            if max_attempts is not None
            else (max_number_of_attempts if max_number_of_attempts is not None else 1)
        )

        # validate inputs
        if first_retry_interval < timedelta(seconds=0):
            raise ValueError('first_retry_interval must be >= 0')
        if resolved_attempts < 1:
            raise ValueError('max_attempts must be >= 1')
        if backoff_coefficient is not None and backoff_coefficient < 1:
            raise ValueError('backoff_coefficient must be >= 1')
        if max_retry_interval is not None and max_retry_interval < timedelta(seconds=0):
            raise ValueError('max_retry_interval must be >= 0')
        if retry_timeout is not None and retry_timeout < timedelta(seconds=0):
            raise ValueError('retry_timeout must be >= 0')

        self._obj = task.RetryPolicy(
            first_retry_interval=first_retry_interval,
            max_number_of_attempts=resolved_attempts,
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
        """The maximum total number of attempts (deprecated alias for max_attempts)."""
        return self._obj._max_number_of_attempts

    @property
    def max_attempts(self) -> int:
        """The maximum total number of attempts (including the initial attempt)."""
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
