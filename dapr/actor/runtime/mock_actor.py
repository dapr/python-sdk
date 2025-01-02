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

from __future__ import annotations

from datetime import timedelta
from typing import Any, Optional, TypeVar

from dapr.actor.id import ActorId
from dapr.actor.runtime._reminder_data import ActorReminderData
from dapr.actor.runtime._timer_data import TIMER_CALLBACK, ActorTimerData
from dapr.actor.runtime.actor import Actor
from dapr.actor.runtime.mock_state_manager import MockStateManager


class MockActor(Actor):
    """A mock actor class to be used to override certain Actor methods for unit testing.
        To be used only via the create_mock_actor function, which takes in a class and returns a
        mock actor object for that class.

    Examples:
        class SomeActorInterface(ActorInterface):
            @actor_method(name="method")
            async def set_state(self, data: dict) -> None:

        class SomeActor(Actor, SomeActorInterface):
            async def set_state(self, data: dict) -> None:
                await self._state_manager.set_state('state', data)
                await self._state_manager.save_state()

        mock_actor = create_mock_actor(SomeActor, "actor_1")
        assert mock_actor._state_manager._mock_state == {}
        await mock_actor.set_state({"test":10})
        assert mock_actor._state_manager._mock_state == {"test":10}
    """

    def __init__(self, actor_id: str, initstate: Optional[dict]):
        self.id = ActorId(actor_id)
        self._runtime_ctx = None  # type: ignore
        self._state_manager = MockStateManager(self, initstate)

    async def register_timer(
        self,
        name: Optional[str],
        callback: TIMER_CALLBACK,
        state: Any,
        due_time: timedelta,
        period: timedelta,
        ttl: Optional[timedelta] = None,
    ) -> None:
        """Adds actor timer to self._state_manager._mock_timers.
        Args:
            name (str): the name of the timer to register.
            callback (Callable): An awaitable callable which will be called when the timer fires.
            state (Any): An object which will pass to the callback method, or None.
            due_time (datetime.timedelta): the amount of time to delay before the awaitable
                callback is first invoked.
            period (datetime.timedelta): the time interval between invocations
                of the awaitable callback.
            ttl (Optional[datetime.timedelta]): the time interval before the timer stops firing
        """
        name = name or self.__get_new_timer_name()
        timer = ActorTimerData(name, callback, state, due_time, period, ttl)
        self._state_manager._mock_timers[name] = timer  # type: ignore

    async def unregister_timer(self, name: str) -> None:
        """Unregisters actor timer from self._state_manager._mock_timers.

        Args:
            name (str): the name of the timer to unregister.
        """
        self._state_manager._mock_timers.pop(name, None)  # type: ignore

    async def register_reminder(
        self,
        name: str,
        state: bytes,
        due_time: timedelta,
        period: timedelta,
        ttl: Optional[timedelta] = None,
    ) -> None:
        """Adds actor reminder to self._state_manager._mock_reminders.

        Args:
            name (str): the name of the reminder to register. the name must be unique per actor.
            state (bytes): the user state passed to the reminder invocation.
            due_time (datetime.timedelta): the amount of time to delay before invoking the reminder
                for the first time.
            period (datetime.timedelta): the time interval between reminder invocations after
                the first invocation.
            ttl (datetime.timedelta): the time interval before the reminder stops firing
        """
        reminder = ActorReminderData(name, state, due_time, period, ttl)
        self._state_manager._mock_reminders[name] = reminder  # type: ignore

    async def unregister_reminder(self, name: str) -> None:
        """Unregisters actor reminder from self._state_manager._mock_reminders..

        Args:
            name (str): the name of the reminder to unregister.
        """
        self._state_manager._mock_reminders.pop(name, None)  # type: ignore


T = TypeVar('T', bound=Actor)


def create_mock_actor(cls1: type[T], actor_id: str, initstate: Optional[dict] = None) -> T:
    class MockSuperClass(MockActor, cls1):  # type: ignore
        pass

    return MockSuperClass(actor_id, initstate)  # type: ignore
