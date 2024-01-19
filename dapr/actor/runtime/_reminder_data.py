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

import base64

from datetime import timedelta
from typing import Any, Dict, Optional


class ActorReminderData:
    """The class that holds actor reminder data.

    Attrtibutes:
        reminder_name: the name of Actor reminder.
        state: the state data data passed to receive_reminder callback.
        due_time: the amount of time to delay before invoking the reminder
            for the first time.
        period: the time interval between reminder invocations after
            the first invocation.
    """

    def __init__(
        self,
        reminder_name: str,
        state: Optional[bytes],
        due_time: timedelta,
        period: timedelta,
        ttl: Optional[timedelta] = None,
    ):
        """Creates new :class:`ActorReminderData` instance.

        Args:
            reminder_name (str): the name of Actor reminder.
            state (bytes, str): the state data passed to
                receive_reminder callback.
            due_time (datetime.timedelta): the amount of time to delay before
                invoking the reminder for the first time.
            period (datetime.timedelta): the time interval between reminder
                invocations after the first invocation.
            ttl (Optional[datetime.timedelta]): the time interval before the reminder stops firing.
        """
        self._reminder_name = reminder_name
        self._due_time = due_time
        self._period = period
        self._ttl = ttl

        if not isinstance(state, bytes):
            raise ValueError(f'only bytes are allowed for state: {type(state)}')

        self._state = state

    @property
    def reminder_name(self) -> str:
        """Gets the name of Actor Reminder."""
        return self._reminder_name

    @property
    def state(self) -> bytes:
        """Gets the state data of Actor Reminder."""
        return self._state

    @property
    def due_time(self) -> timedelta:
        """Gets due_time of Actor Reminder."""
        return self._due_time

    @property
    def period(self) -> timedelta:
        """Gets period of Actor Reminder."""
        return self._period

    @property
    def ttl(self) -> Optional[timedelta]:
        """Gets ttl of Actor Reminder."""
        return self._ttl

    def as_dict(self) -> Dict[str, Any]:
        """Gets :class:`ActorReminderData` as a dict object."""
        encoded_state = None
        if self._state is not None:
            encoded_state = base64.b64encode(self._state)
        reminderDict: Dict[str, Any] = {
            'reminderName': self._reminder_name,
            'dueTime': self._due_time,
            'period': self._period,
            'data': encoded_state.decode('utf-8'),
        }

        if self._ttl is not None:
            reminderDict.update({'ttl': self._ttl})

        return reminderDict

    @classmethod
    def from_dict(cls, reminder_name: str, obj: Dict[str, Any]) -> 'ActorReminderData':
        """Creates :class:`ActorReminderData` object from dict object."""
        b64encoded_state = obj.get('data')
        state_bytes = None
        if b64encoded_state is not None and len(b64encoded_state) > 0:
            state_bytes = base64.b64decode(b64encoded_state)
        if 'ttl' in obj:
            return ActorReminderData(
                reminder_name, state_bytes, obj['dueTime'], obj['period'], obj['ttl']
            )
        else:
            return ActorReminderData(reminder_name, state_bytes, obj['dueTime'], obj['period'])
