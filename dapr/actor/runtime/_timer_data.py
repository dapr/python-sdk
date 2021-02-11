# -*- coding: utf-8 -*-

"""
Copyright (c) Microsoft Corporation and Dapr Contributors.
Licensed under the MIT License.
"""

from datetime import timedelta
from typing import Any, Awaitable, Callable, Dict

TIMER_CALLBACK = Callable[[Any], Awaitable[None]]


class ActorTimerData:
    """The class that holds actor timer data.

    Attributes:
        timer_name: the name of Actor timer.
        state: the state object passed to timer callback.
        due_time: the amount of time to delay before the first timer trigger.
        period: the time interval between reminder invocations after
            the first timer trigger.
        callback: timer callback when timer is triggered.
    """

    def __init__(
            self, timer_name: str,
            callback: TIMER_CALLBACK, state: Any,
            due_time: timedelta, period: timedelta):
        """Create new :class:`ActorTimerData` instance.

        Args:
            timer_name (str): the name of Actor timer.
            callback (TIMER_CALLBACK): timer callback when timer is triggered.
            state (Any): the state object passed to timer callback.
            due_time (datetime.timedelta): the amount of time to delay
                before the first timer trigger.
            period (datetime.timedelta): the time interval between reminder
                invocations after the first timer trigger.
        """
        self._timer_name = timer_name
        self._callback = callback.__name__
        self._state = state
        self._due_time = due_time
        self._period = period

    @property
    def timer_name(self) -> str:
        """Gets the name of the actor timer."""
        return self._timer_name

    @property
    def state(self) -> Any:
        """Gets the state object of the actor timer."""
        return self._state

    @property
    def due_time(self) -> timedelta:
        """Gets due_timer of the actor timer."""
        return self._due_time

    @property
    def period(self) -> timedelta:
        """Gets period of the actor timer."""
        return self._period

    @property
    def callback(self) -> str:
        """Gets the callback of the actor timer."""
        return self._callback

    def as_dict(self) -> Dict[str, Any]:
        """Returns :class:`ActorTimerData` object as a dict.

        This is used to serialize Actor Timer Data for Dapr runtime API.
        """

        return {
            'callback': self._callback,
            'data': self._state,
            'dueTime': self._due_time,
            'period': self._period,
        }
