# -*- coding: utf-8 -*-

"""
Copyright (c) Microsoft Corporation.
Licensed under the MIT License.
"""

import base64

from datetime import timedelta
from typing import Any, Dict


class ActorReminderData:
    """represents Actor reminder data."""
    def __init__(
            self, name: str, state: bytes,
            due_time: timedelta, period: timedelta):
        self._name = name
        self._state = state
        self._due_time = due_time
        self._period = period

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
            'state': encoded_state,
        }

    @classmethod
    def from_dict(cls, obj: Dict[str, Any]) -> 'ActorReminderData':
        b64encoded_state = obj.get('state')
        state_bytes = None
        if b64encoded_state is not None and len(b64encoded_state) > 0:
            state_bytes = base64.b64decode(b64encoded_state)
        return cls(obj['name'], state_bytes, obj['dueTime'], obj['period'])
