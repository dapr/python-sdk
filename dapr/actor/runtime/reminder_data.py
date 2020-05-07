# -*- coding: utf-8 -*-

"""
Copyright (c) Microsoft Corporation.
Licensed under the MIT License.
"""

from datetime import timedelta
from typing import Any


class ActorReminderData:
    """represents Actor reminder data."""
    def __init__(
            self, name: str, state: Any,
            due_time: timedelta, period: timedelta):
        self._name = name
        self._state = state
        self._due_time = due_time
        self._period = period

    @property
    def name(self) -> str:
        return self._name

    @property
    def state(self) -> Any:
        return self._state

    @property
    def due_time(self) -> timedelta:
        return self._due_time

    @property
    def period(self) -> timedelta:
        return self._period
