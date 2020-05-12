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
        """A callback which will be called when reminder is triggered.

        :param str name: the name of the reminder to register. the name must be unique per actor.
        :param bytes state: the user state passed to the reminder invocation.
        :param datetime.timedelta due_time: the amount of time to delay before invoking the reminder
                                            for the first time.
        :param datetime.timedelta period: the time interval between reminder invocations
                                          after the first invocation.
        """
        ...
