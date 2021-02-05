# -*- coding: utf-8 -*-

"""
Copyright (c) Microsoft Corporation and Dapr Contributors.
Licensed under the MIT License.
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
            self, reminder_name: str, state: Optional[bytes],
            due_time: timedelta, period: timedelta):
        """Creates new :class:`ActorReminderData` instance.

        Args:
            reminder_name (str): the name of Actor reminder.
            state (bytes, str): the state data passed to
                receive_reminder callback.
            due_time (datetime.timedelta): the amount of time to delay before
                invoking the reminder for the first time.
            period (datetime.timedelta): the time interval between reminder
                invocations after the first invocation.
        """
        self._reminder_name = reminder_name
        self._due_time = due_time
        self._period = period

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

    def as_dict(self) -> Dict[str, Any]:
        """Gets :class:`ActorReminderData` as a dict object."""
        encoded_state = None
        if self._state is not None:
            encoded_state = base64.b64encode(self._state)
        return {
            'reminderName': self._reminder_name,
            'dueTime': self._due_time,
            'period': self._due_time,
            'data': encoded_state.decode("utf-8"),
        }

    @classmethod
    def from_dict(cls, reminder_name: str, obj: Dict[str, Any]) -> 'ActorReminderData':
        """Creates :class:`ActorReminderData` object from dict object."""
        b64encoded_state = obj.get('data')
        state_bytes = None
        if b64encoded_state is not None and len(b64encoded_state) > 0:
            state_bytes = base64.b64decode(b64encoded_state)
        return ActorReminderData(reminder_name, state_bytes, obj['dueTime'], obj['period'])
