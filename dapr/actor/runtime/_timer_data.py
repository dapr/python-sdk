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
from typing import Any, Awaitable, Callable, Dict, Optional

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
        ttl: the time interval before the timer stops firing.
    """

    def __init__(
        self,
        timer_name: str,
        callback: TIMER_CALLBACK,
        state: Any,
        due_time: timedelta,
        period: timedelta,
        ttl: Optional[timedelta] = None,
    ):
        """Create new :class:`ActorTimerData` instance.

        Args:
            timer_name (str): the name of Actor timer.
            callback (TIMER_CALLBACK): timer callback when timer is triggered.
            state (Any): the state object passed to timer callback.
            due_time (datetime.timedelta): the amount of time to delay
                before the first timer trigger.
            period (datetime.timedelta): the time interval between reminder
                invocations after the first timer trigger.
            ttl (Optional[datetime.timedelta]): the time interval before the timer stops firing.
        """
        self._timer_name = timer_name
        self._callback = callback.__name__
        self._state = state
        self._due_time = due_time
        self._period = period
        self._ttl = ttl

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
    def ttl(self) -> Optional[timedelta]:
        """Gets ttl of the actor timer."""
        return self._ttl

    @property
    def callback(self) -> str:
        """Gets the callback of the actor timer."""
        return self._callback

    def as_dict(self) -> Dict[str, Any]:
        """Returns :class:`ActorTimerData` object as a dict.

        This is used to serialize Actor Timer Data for Dapr runtime API.
        """

        timerDict: Dict[str, Any] = {
            'callback': self._callback,
            'data': self._state,
            'dueTime': self._due_time,
            'period': self._period,
        }

        if self._ttl:
            timerDict.update({'ttl': self._ttl})

        return timerDict
