import datetime
import unittest
from abc import abstractmethod
from typing import Optional

from dapr.actor import Actor, ActorInterface, Remindable, actormethod
from dapr.actor.runtime.mock_actor import create_mock_actor


class DemoActorInterface(ActorInterface):
    @abstractmethod
    @actormethod(name='GetData')
    async def get_data(self) -> object: ...

    @abstractmethod
    @actormethod(name='SetData')
    async def set_data(self, data: object) -> None: ...

    @abstractmethod
    @actormethod(name='ClearData')
    async def clear_data(self) -> None: ...

    @abstractmethod
    @actormethod(name='ToggleReminder')
    async def toggle_reminder(self, name: str, enabled: bool) -> None: ...

    @abstractmethod
    @actormethod(name='ToggleTimer')
    async def toggle_timer(self, name: str, enabled: bool) -> None: ...


class DemoActor(Actor, DemoActorInterface, Remindable):
    """Implements DemoActor actor service

    This shows the usage of the below actor features:

    1. Actor method invocation
    2. Actor state store management
    3. Actor reminder
    4. Actor timer
    """

    def __init__(self, ctx, actor_id):
        super().__init__(ctx, actor_id)

    async def _on_activate(self) -> None:
        await self._state_manager.set_state('state', {'test': 5})
        await self._state_manager.save_state()

    async def get_data(self) -> object:
        _, val = await self._state_manager.try_get_state('state')
        return val

    async def set_data(self, data) -> None:
        await self._state_manager.set_state('state', data)
        await self._state_manager.save_state()

    async def clear_data(self) -> None:
        await self._state_manager.remove_state('state')
        await self._state_manager.save_state()

    async def toggle_reminder(self, name: str, enabled: bool) -> None:
        if enabled:
            await self.register_reminder(
                name,
                b'reminder_state',
                datetime.timedelta(seconds=5),
                datetime.timedelta(seconds=10),
                datetime.timedelta(seconds=15),
            )
        else:
            await self.unregister_reminder(name)

    async def toggle_timer(self, name:str, enabled:bool) -> None:
        if enabled:
            await self.register_timer(
                name,
                self.timer_callback,
                'timer_state',
                datetime.timedelta(seconds=5),
                datetime.timedelta(seconds=10),
                datetime.timedelta(seconds=15),
            )
        else:
            await self.unregister_timer(name)

    async def receive_reminder(
        self,
        name: str,
        state: bytes,
        due_time: datetime.timedelta,
        period: datetime.timedelta,
        ttl: Optional[datetime.timedelta] = None,
    ) -> None:
        print('Reminder triggered')

    async def timer_callback(self, state) -> None:
        print('Timer triggered')

class ActorMockActorTests(unittest.IsolatedAsyncioTestCase):
    def test_create_actor(self):
        mockactor = create_mock_actor(DemoActor, "1")
        self.assertEqual(mockactor.id.id, "1")

    async def test_on_activate(self):
        mockactor = create_mock_actor(DemoActor, "1")
        await mockactor._on_activate()
        self.assertTrue("state" in mockactor._mock_state)
        self.assertEqual(mockactor._mock_state["state"], {'test': 5})