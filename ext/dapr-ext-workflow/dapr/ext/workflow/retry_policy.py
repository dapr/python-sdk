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
    """Retry policy for workflow activities and child workflows.

    A ``RetryPolicy`` is passed to ``ctx.call_activity()`` or
    ``ctx.call_child_workflow()`` to automatically retry the task when it
    fails. The first attempt always runs; on failure, the engine waits
    ``first_retry_interval`` before the second attempt and multiplies the
    wait by ``backoff_coefficient`` after each subsequent failure,
    optionally capped per-attempt by ``max_retry_interval``.

    Example::

        from datetime import timedelta
        from dapr.ext.workflow import RetryPolicy

        policy = RetryPolicy(
            first_retry_interval=timedelta(seconds=1),
            max_attempts=5,
            backoff_coefficient=2.0,
            max_retry_interval=timedelta(seconds=30),
        )

        result = yield ctx.call_activity(my_activity, input=data, retry_policy=policy)

    Notes:
        * ``max_attempts`` (or its deprecated alias ``max_number_of_attempts``)
          is the **total** number of attempts, not the number of retries.
          A value of ``5`` means up to 4 retries after the first attempt.
        * If ``retry_timeout`` elapses before the next scheduled attempt,
          the task fails with the last error. The surrounding workflow
          will then fail unless the call is wrapped in ``try`` / ``except``
          in the workflow function.
        * ``max_retry_interval`` only caps the per-attempt delay; retries
          still proceed when it is left as ``None``.
    """

    def __init__(
        self,
        *,
        first_retry_interval: timedelta,
        max_number_of_attempts: Optional[int] = None,
        backoff_coefficient: Optional[float] = 1.0,
        max_retry_interval: Optional[timedelta] = None,
        retry_timeout: Optional[timedelta] = None,
        max_attempts: Optional[int] = None,
    ):
        """Create a new RetryPolicy.

        Args:
            first_retry_interval: Delay between the first attempt and the
                first retry (attempt #2). Must be ``>= 0``.
            max_number_of_attempts: **Deprecated** alias for ``max_attempts``,
                kept for backward compatibility. Exactly one of
                ``max_attempts`` or ``max_number_of_attempts`` must be
                provided.
            backoff_coefficient: Exponential backoff multiplier applied to
                successive retry intervals. Must be ``>= 1``. Defaults to
                ``1.0`` (constant delay between retries).
            max_retry_interval: Upper bound on the delay between any two
                consecutive attempts. When ``None`` (the default) the
                delay grows unbounded according to the backoff. Retries
                still occur when this is ``None``; it only caps the
                per-attempt delay.
            retry_timeout: Total budget for the retry sequence, measured
                from when the task first started. If the next attempt
                would start after this deadline, the task fails
                immediately with the last error. ``None`` (the default)
                means no timeout. When the timeout fires, the surrounding
                workflow handles the failure like any other task failure:
                the workflow fails unless the call is wrapped in
                ``try`` / ``except``.
            max_attempts: Total number of attempts the task may run,
                including the first one. Must be ``>= 1``. Exactly one of
                ``max_attempts`` or ``max_number_of_attempts`` must be
                provided.

        Raises:
            ValueError: If neither or both of ``max_attempts`` and
                ``max_number_of_attempts`` are provided, or if any other
                field fails its range check.
        """
        attempts_resolved = _resolve_max_attempts(
            max_attempts=max_attempts,
            max_number_of_attempts=max_number_of_attempts,
        )

        if first_retry_interval < timedelta(seconds=0):
            raise ValueError('first_retry_interval must be >= 0')
        if attempts_resolved < 1:
            raise ValueError('max_attempts must be >= 1')
        if backoff_coefficient is not None and backoff_coefficient < 1:
            raise ValueError('backoff_coefficient must be >= 1')
        if max_retry_interval is not None and max_retry_interval < timedelta(seconds=0):
            raise ValueError('max_retry_interval must be >= 0')
        if retry_timeout is not None and retry_timeout < timedelta(seconds=0):
            raise ValueError('retry_timeout must be >= 0')

        self._obj = task.RetryPolicy(
            first_retry_interval=first_retry_interval,
            max_number_of_attempts=attempts_resolved,
            backoff_coefficient=backoff_coefficient,
            max_retry_interval=max_retry_interval,
            retry_timeout=retry_timeout,
        )

    @property
    def obj(self) -> task.RetryPolicy:
        """The underlying durabletask ``RetryPolicy`` instance."""
        return self._obj

    @property
    def first_retry_interval(self) -> timedelta:
        """Delay between the first attempt and the first retry."""
        return self._obj._first_retry_interval

    @property
    def max_number_of_attempts(self) -> int:
        """Total number of attempts (alias of :attr:`max_attempts`).

        Kept for backward compatibility. New code should prefer
        :attr:`max_attempts`, which has the same value but a clearer name.
        """
        return self._obj._max_number_of_attempts

    @property
    def max_attempts(self) -> int:
        """Total number of attempts (including the first one)."""
        return self._obj._max_number_of_attempts

    @property
    def backoff_coefficient(self) -> Optional[float]:
        """Multiplier applied to the retry interval after each failure."""
        return self._obj._backoff_coefficient

    @property
    def max_retry_interval(self) -> Optional[timedelta]:
        """Upper bound on the per-attempt retry delay (``None`` for no cap)."""
        return self._obj._max_retry_interval

    @property
    def retry_timeout(self) -> Optional[timedelta]:
        """Total time budget for retries (``None`` for no timeout).

        When the timeout fires, the task fails with the last error and the
        surrounding workflow fails unless the call is wrapped in
        ``try`` / ``except``.
        """
        return self._obj._retry_timeout


def _resolve_max_attempts(
    *,
    max_attempts: Optional[int],
    max_number_of_attempts: Optional[int],
) -> int:
    """Pick between ``max_attempts`` and its deprecated alias.

    Exactly one of the two names must be supplied. Supplying both is
    rejected to avoid silent inconsistencies between the values.
    """
    if max_attempts is not None and max_number_of_attempts is not None:
        raise ValueError(
            'Specify only one of max_attempts or max_number_of_attempts; '
            'max_number_of_attempts is a deprecated alias.'
        )
    if max_attempts is not None:
        return max_attempts
    if max_number_of_attempts is not None:
        return max_number_of_attempts
    raise ValueError('max_attempts is required (max_number_of_attempts is a deprecated alias).')
