# -*- coding: utf-8 -*-

"""
Copyright 2021 The Dapr Authors
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

from abc import ABC, abstractmethod
from datetime import timedelta
from typing import Optional


class Remindable(ABC):
    """An interface that actors must implement to consume reminders registered
    using :meth:`Remindable.register_reminder`.
    """

    @abstractmethod
    async def receive_reminder(self, name: str, state: bytes,
                               due_time: timedelta, period: timedelta,
                               ttl: Optional[timedelta] = None) -> None:
        """A callback which will be called when reminder is triggered.

        Args:
            name (str): the name of the reminder to register. the name must be unique per actor.
            state (bytes): the user state passed to the reminder invocation.
            due_time (datetime.timedelta): the amount of time to delay before invoking the reminder
                for the first time.
            period (datetime.timedelta): the time interval between reminder invocations
                after the first invocation.
            ttl (datetime.timedelta): the time interval before the reminder stops firing
        """
        ...
