import datetime
import unittest
from typing import Optional

from dapr.actor import Actor, ActorInterface, Remindable, actormethod
from dapr.actor.runtime.mock_actor import create_mock_actor
from dapr.actor.runtime.state_change import StateChangeKind


class MockTestActorInterface(ActorInterface):
    @actormethod(name='GetData')
    async def get_data(self) -> object:
        ...

    @actormethod(name='SetData')
    async def set_data(self, data: object) -> None:
        ...

    @actormethod(name='ClearData')
    async def clear_data(self) -> None:
        ...

    @actormethod(name='TestData')
    async def test_data(self) -> int:
        ...

    @actormethod(name='AddState')
    async def add_state(self, name: str, data: object) -> None:
        ...

    @actormethod(name='UpdateState')
    async def update_state(self, name: str, data: object) -> None:
        ...

    @actormethod(name='AddDataNoSave')
    async def add_data_no_save(self, data: object) -> None:
        ...

    @actormethod(name='RemoveDataNoSave')
    async def remove_data_no_save(self) -> None:
        ...

    @actormethod(name='SaveState')
    async def save_state(self) -> None:
        ...

    @actormethod(name='ToggleReminder')
    async def toggle_reminder(self, name: str, enabled: bool) -> None:
        ...

    @actormethod(name='ToggleTimer')
    async def toggle_timer(self, name: str, enabled: bool) -> None:
        ...


class MockTestActor(Actor, MockTestActorInterface, Remindable):
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

    async def test_data(self) -> int:
        _, val = await self._state_manager.try_get_state('state')
        if val is None:
            return 0
        if 'test' not in val:
            return 1
        if val['test'] % 2 == 1:
            return 2
        elif val['test'] % 2 == 0:
            return 3
        return 4

    async def add_state(self, name: str, data: object) -> None:
        await self._state_manager.add_state(name, data)

    async def update_state(self, name: str, data: object) -> None:
        def double(_: str, x: int) -> int:
            return 2 * x

        await self._state_manager.add_or_update_state(name, data, double)

    async def add_data_no_save(self, data: object) -> None:
        await self._state_manager.set_state('state', data)

    async def remove_data_no_save(self) -> None:
        await self._state_manager.remove_state('state')

    async def save_state(self) -> None:
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

    async def toggle_timer(self, name: str, enabled: bool) -> None:
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
        await self._state_manager.set_state(name, True)
        await self._state_manager.save_state()

    async def timer_callback(self, state) -> None:
        print('Timer triggered')


class ActorMockActorTests(unittest.IsolatedAsyncioTestCase):
    def test_create_actor(self):
        mockactor = create_mock_actor(MockTestActor, '1')
        self.assertEqual(mockactor.id.id, '1')

    async def test_inistate(self):
        mockactor = create_mock_actor(MockTestActor, '1', initstate={'state': 5})
        self.assertTrue('state' in mockactor._state_manager._mock_state)
        self.assertEqual(mockactor._state_manager._mock_state['state'], 5)

    async def test_on_activate(self):
        mockactor = create_mock_actor(MockTestActor, '1')
        await mockactor._on_activate()
        self.assertTrue('state' in mockactor._state_manager._mock_state)
        self.assertEqual(mockactor._state_manager._mock_state['state'], {'test': 5})

    async def test_get_data(self):
        mockactor = create_mock_actor(MockTestActor, '1')
        await mockactor._on_activate()
        out1 = await mockactor.get_data()
        self.assertEqual(out1, {'test': 5})

    async def test_get_data_initstate(self):
        mockactor = create_mock_actor(MockTestActor, '1', initstate={'state': {'test': 6}})
        out1 = await mockactor.get_data()
        self.assertEqual(out1, {'test': 6})

    async def test_set_data(self):
        mockactor = create_mock_actor(MockTestActor, '1')
        await mockactor._on_activate()
        self.assertTrue('state' in mockactor._state_manager._mock_state)
        self.assertEqual(mockactor._state_manager._mock_state['state'], {'test': 5})
        await mockactor.set_data({'test': 10})
        self.assertTrue('state' in mockactor._state_manager._mock_state)
        self.assertEqual(mockactor._state_manager._mock_state['state'], {'test': 10})
        out1 = await mockactor.get_data()
        self.assertEqual(out1, {'test': 10})

    async def test_clear_data(self):
        mockactor = create_mock_actor(MockTestActor, '1')
        await mockactor._on_activate()
        self.assertTrue('state' in mockactor._state_manager._mock_state)
        self.assertEqual(mockactor._state_manager._mock_state['state'], {'test': 5})
        await mockactor.clear_data()
        self.assertFalse('state' in mockactor._state_manager._mock_state)
        self.assertIsNone(mockactor._state_manager._mock_state.get('state'))
        out1 = await mockactor.get_data()
        self.assertIsNone(out1)

    async def test_toggle_reminder(self):
        mockactor = create_mock_actor(MockTestActor, '1')
        await mockactor._on_activate()
        self.assertEqual(len(mockactor._state_manager._mock_reminders), 0)
        await mockactor.toggle_reminder('test', True)
        self.assertEqual(len(mockactor._state_manager._mock_reminders), 1)
        self.assertTrue('test' in mockactor._state_manager._mock_reminders)
        reminderstate = mockactor._state_manager._mock_reminders['test']
        self.assertTrue(reminderstate.reminder_name, 'test')
        await mockactor.toggle_reminder('test', False)
        self.assertEqual(len(mockactor._state_manager._mock_reminders), 0)

    async def test_toggle_timer(self):
        mockactor = create_mock_actor(MockTestActor, '1')
        await mockactor._on_activate()
        self.assertEqual(len(mockactor._state_manager._mock_timers), 0)
        await mockactor.toggle_timer('test', True)
        self.assertEqual(len(mockactor._state_manager._mock_timers), 1)
        self.assertTrue('test' in mockactor._state_manager._mock_timers)
        timerstate = mockactor._state_manager._mock_timers['test']
        self.assertTrue(timerstate.timer_name, 'test')
        await mockactor.toggle_timer('test', False)
        self.assertEqual(len(mockactor._state_manager._mock_timers), 0)

    async def test_activate_reminder(self):
        mockactor = create_mock_actor(MockTestActor, '1')
        await mockactor.receive_reminder(
            'test',
            b'test1',
            datetime.timedelta(days=1),
            datetime.timedelta(days=1),
            datetime.timedelta(days=1),
        )
        self.assertEqual(mockactor._state_manager._mock_state['test'], True)

    async def test_test_data(self):
        mockactor = create_mock_actor(MockTestActor, '1')
        result = await mockactor.test_data()
        self.assertEqual(result, 0)
        await mockactor.set_data('lol')
        result = await mockactor.test_data()
        self.assertEqual(result, 1)
        await mockactor.set_data({'test': 'lol'})
        with self.assertRaises(TypeError):
            await mockactor.test_data()
        await mockactor.set_data({'test': 1})
        result = await mockactor.test_data()
        self.assertEqual(result, 2)
        await mockactor.set_data({'test': 2})
        result = await mockactor.test_data()
        self.assertEqual(result, 3)

    async def test_add_state(self):
        mockactor = create_mock_actor(MockTestActor, '1')
        print(mockactor._state_manager._mock_state)
        self.assertFalse(mockactor._state_manager._mock_state)
        await mockactor.add_state('test', 5)
        self.assertTrue('test' in mockactor._state_manager._mock_state)
        self.assertEqual(mockactor._state_manager._mock_state['test'], 5)
        await mockactor.add_state('test2', 10)
        self.assertTrue('test2' in mockactor._state_manager._mock_state)
        self.assertEqual(mockactor._state_manager._mock_state['test2'], 10)
        self.assertEqual(len(mockactor._state_manager._mock_state), 2)
        with self.assertRaises(ValueError):
            await mockactor.add_state('test', 10)

    async def test_update_state(self):
        mockactor = create_mock_actor(MockTestActor, '1')
        self.assertFalse(mockactor._state_manager._mock_state)
        await mockactor.update_state('test', 10)
        self.assertTrue('test' in mockactor._state_manager._mock_state)
        self.assertEqual(mockactor._state_manager._mock_state['test'], 10)
        await mockactor.update_state('test', 10)
        self.assertTrue('test' in mockactor._state_manager._mock_state)
        self.assertEqual(mockactor._state_manager._mock_state['test'], 20)
        self.assertEqual(len(mockactor._state_manager._mock_state), 1)

    async def test_state_change_tracker(self):
        mockactor = create_mock_actor(MockTestActor, '1')
        self.assertEqual(len(mockactor._state_manager._default_state_change_tracker), 0)
        await mockactor._on_activate()
        self.assertEqual(len(mockactor._state_manager._default_state_change_tracker), 1)
        self.assertTrue('state' in mockactor._state_manager._default_state_change_tracker)
        self.assertEqual(
            mockactor._state_manager._default_state_change_tracker['state'].change_kind,
            StateChangeKind.none,
        )
        self.assertEqual(
            mockactor._state_manager._default_state_change_tracker['state'].value, {'test': 5}
        )
        self.assertEqual(mockactor._state_manager._mock_state['state'], {'test': 5})
        await mockactor.remove_data_no_save()
        self.assertEqual(
            mockactor._state_manager._default_state_change_tracker['state'].change_kind,
            StateChangeKind.remove,
        )
        self.assertEqual(
            mockactor._state_manager._default_state_change_tracker['state'].value, {'test': 5}
        )
        self.assertTrue('state' not in mockactor._state_manager._mock_state)
        await mockactor.save_state()
        self.assertEqual(len(mockactor._state_manager._default_state_change_tracker), 0)
        self.assertTrue('state' not in mockactor._state_manager._mock_state)
        await mockactor.add_data_no_save({'test': 6})
        self.assertEqual(
            mockactor._state_manager._default_state_change_tracker['state'].change_kind,
            StateChangeKind.add,
        )
        self.assertEqual(
            mockactor._state_manager._default_state_change_tracker['state'].value, {'test': 6}
        )
        self.assertEqual(mockactor._state_manager._mock_state['state'], {'test': 6})
        await mockactor.save_state()
        self.assertEqual(
            mockactor._state_manager._default_state_change_tracker['state'].change_kind,
            StateChangeKind.none,
        )
        self.assertEqual(
            mockactor._state_manager._default_state_change_tracker['state'].value, {'test': 6}
        )
        self.assertEqual(mockactor._state_manager._mock_state['state'], {'test': 6})
