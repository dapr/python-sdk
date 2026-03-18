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

from datetime import timedelta
from typing import Any, Dict, Optional


class ActorReminderFailurePolicy:
    """Defines what happens when an actor reminder fails to trigger.

    Use :meth:`drop_policy` to discard failed ticks without retrying, or
    :meth:`constant_policy` to retry at a fixed interval.

    Attributes:
        drop: whether this is a drop (no-retry) policy.
        interval: the retry interval for a constant policy.
        max_retries: the maximum number of retries for a constant policy.
    """

    def __init__(
        self,
        *,
        drop: bool = False,
        interval: Optional[timedelta] = None,
        max_retries: Optional[int] = None,
    ):
        """Creates a new :class:`ActorReminderFailurePolicy` instance.

        Args:
            drop (bool): if True, creates a drop policy that discards the reminder
                tick on failure without retrying. Cannot be combined with interval
                or max_retries.
            interval (datetime.timedelta): the retry interval for a constant policy.
            max_retries (int): the maximum number of retries for a constant policy.
                If not set, retries indefinitely.

        Raises:
            ValueError: if drop is combined with interval or max_retries, or if
                neither drop=True nor at least one of interval/max_retries is provided.
        """
        if drop and (interval is not None or max_retries is not None):
            raise ValueError('drop policy cannot be combined with interval or max_retries')
        if not drop and interval is None and max_retries is None:
            raise ValueError('specify either drop=True or at least one of interval or max_retries')
        self._drop = drop
        self._interval = interval
        self._max_retries = max_retries

    @classmethod
    def drop_policy(cls) -> 'ActorReminderFailurePolicy':
        """Returns a policy that drops the reminder tick on failure (no retry)."""
        return cls(drop=True)

    @classmethod
    def constant_policy(
        cls,
        interval: Optional[timedelta] = None,
        max_retries: Optional[int] = None,
    ) -> 'ActorReminderFailurePolicy':
        """Returns a policy that retries at a constant interval on failure.

        Args:
            interval (datetime.timedelta): the time between retry attempts.
            max_retries (int): the maximum number of retry attempts. If not set,
                retries indefinitely.
        """
        return cls(interval=interval, max_retries=max_retries)

    @property
    def drop(self) -> bool:
        """Returns True if this is a drop policy."""
        return self._drop

    @property
    def interval(self) -> Optional[timedelta]:
        """Returns the retry interval for a constant policy."""
        return self._interval

    @property
    def max_retries(self) -> Optional[int]:
        """Returns the maximum retries for a constant policy."""
        return self._max_retries

    def as_dict(self) -> Dict[str, Any]:
        """Gets :class:`ActorReminderFailurePolicy` as a dict object."""
        if self._drop:
            return {'drop': {}}
        d: Dict[str, Any] = {}
        if self._interval is not None:
            d['interval'] = self._interval
        if self._max_retries is not None:
            d['maxRetries'] = self._max_retries
        return {'constant': d}
