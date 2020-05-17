# -*- coding: utf-8 -*-

"""
Copyright (c) Microsoft Corporation.
Licensed under the MIT License.
"""

import base64

from datetime import timedelta
from typing import Any, Dict


class ActorReminderData:
    """Represents Actor reminder data."""

    def __init__(
            self, name: str, state: bytes,
            due_time: timedelta, period: timedelta):
        self._name = name
        self._due_time = due_time
        self._period = period

        if not isinstance(state, (str, bytes)):
            raise ValueError(f'only str and bytes are allowed for state: {type(state)}')

        if isinstance(state, str):
            self._state = state.encode('utf-8')
        else:
            self._state = state

    @property
    def name(self) -> str:
        return self._name

    @property
    def state(self) -> bytes:
        return self._state

    @property
    def due_time(self) -> timedelta:
        return self._due_time

    @property
    def period(self) -> timedelta:
        return self._period

    def as_dict(self) -> dict:
        encoded_state = None
        if self._state is not None:
            encoded_state = base64.b64encode(self._state)
        return {
            'name': self._name,
            'dueTime': self._due_time,
            'period': self._due_time,
            'data': encoded_state.decode("utf-8"),
        }

    @classmethod
    def from_dict(cls, obj: Dict[str, Any]) -> 'ActorReminderData':
        b64encoded_state = obj.get('data')
        state_bytes = None
        if b64encoded_state is not None and len(b64encoded_state) > 0:
            state_bytes = base64.b64decode(b64encoded_state)
        return ActorReminderData(obj['name'], state_bytes, obj['dueTime'], obj['period'])
