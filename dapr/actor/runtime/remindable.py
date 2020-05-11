# -*- coding: utf-8 -*-

"""
Copyright (c) Microsoft Corporation.
Licensed under the MIT License.
"""

from abc import ABC, abstractmethod
from datetime import timedelta


class Remindable(ABC):
    """An interface that actors must implement to consume reminders registered
    using `:Actor:register_reminder`.
    """
    @abstractmethod
    async def receive_reminder(self, name: str, state: bytes,
                               due_time: timedelta, period: timedelta) -> None:
        ...
