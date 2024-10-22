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
from typing import Any, Optional, TypeVar

from dapr.actor.id import ActorId
from dapr.actor.runtime._reminder_data import ActorReminderData
from dapr.actor.runtime._timer_data import TIMER_CALLBACK, ActorTimerData
from dapr.actor.runtime.actor import Actor
from dapr.actor.runtime.mock_state_manager import MockStateManager
from dapr.actor.runtime.state_manager import ActorStateManager


class MockActor(Actor):
    """A base class of Actors that provides the common functionality of actors.

    Examples:

        class DaprActorInterface(ActorInterface):
            @actor_method(name="method")
            async def method_invoke(self, arg: str) -> str:
                ...

        class DaprActor(Actor, DaprActorInterface):
            def __init__(self, ctx, actor_id):
                super(DaprActor, self).__init__(ctx, actor_id)

            async def method_invoke(self, arg: str) -> str:
                return arg

            async def _on_activate(self):
                pass

            async def _on_deactivate(self):
                pass

    Attributes:
        runtime_ctx: the :class:`ActorRuntimeContext` object served for
            the actor implementation.
    """

    def __init__(self, actor_id: str, initstate: Optional[dict]):
        self.id = ActorId(actor_id)
        self._runtime_ctx = None
        if initstate is not None:
            self._mock_state = initstate
        self._state_manager: ActorStateManager = MockStateManager(self)

    async def register_timer(
        self,
        name: Optional[str],
        callback: TIMER_CALLBACK,
        state: Any,
        due_time: timedelta,
        period: timedelta,
        ttl: Optional[timedelta] = None,
    ) -> None:
        """Registers actor timer.

        All timers are stopped when the actor is deactivated as part of garbage collection.

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
        self._state_manager._mock_timers[name] = timer

    async def unregister_timer(self, name: str) -> None:
        """Unregisters actor timer.

        Args:
            name (str): the name of the timer to unregister.
        """
        self._state_manager._mock_timers.pop(name, None)

    async def register_reminder(
        self,
        name: str,
        state: bytes,
        due_time: timedelta,
        period: timedelta,
        ttl: Optional[timedelta] = None,
    ) -> None:
        """Registers actor reminder.

        Reminders are a mechanism to trigger persistent callbacks on an actor at specified times.
        Their functionality is similar to timers. But unlike timers, reminders are triggered under
        all circumstances until the actor explicitly unregisters them or the actor is explicitly
        deleted. Specifically, reminders are triggered across actor deactivations and failovers
        because the Actors runtime persists information about the actor's reminders using actor
        state provider. Also existing reminders can be updated by calling this registration method
        again using the same reminderName.

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
        self._state_manager._mock_reminders[name] = reminder

    async def unregister_reminder(self, name: str) -> None:
        """Unregisters actor reminder.

        Args:
            name (str): the name of the reminder to unregister.
        """
        self._state_manager._mock_reminders.pop(name, None)


T = TypeVar('T', bound=Actor)


def create_mock_actor(cls1: type[T], actor_id: str, initstate: Optional[dict] = None) -> T:
    class MockSuperClass(MockActor, cls1):
        pass
    return MockSuperClass(actor_id, initstate)  # type: ignore
