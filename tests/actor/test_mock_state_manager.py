import unittest

from dapr.actor import Actor, ActorInterface
from dapr.actor.runtime.mock_actor import create_mock_actor
from dapr.actor.runtime.mock_state_manager import MockStateManager


def double(_: str, x: int) -> int:
    return 2 * x


class MockTestActorInterface(ActorInterface):
    pass


class MockTestActor(Actor, MockTestActorInterface):
    def __init__(self, ctx, actor_id):
        super().__init__(ctx, actor_id)


class ActorMockActorTests(unittest.IsolatedAsyncioTestCase):
    def test_init_state(self):
        mock_actor = create_mock_actor(MockTestActor, 'test')
        state_manager = mock_actor._state_manager
        self.assertIsInstance(state_manager, MockStateManager)
        self.assertFalse(state_manager._mock_state)
        self.assertFalse(state_manager._mock_reminders)
        self.assertFalse(state_manager._mock_timers)

    async def test_add_state(self):
        mock_actor = create_mock_actor(MockTestActor, 'test')
        state_manager = mock_actor._state_manager
        await state_manager.add_state('state', 5)
        self.assertIs(state_manager._mock_state['state'], 5)
        await state_manager.add_state('state2', 5)
        self.assertIs(state_manager._mock_state['state2'], 5)
        with self.assertRaises(ValueError):
            await state_manager.add_state('state', 5)

    async def test_get_state(self):
        mock_actor = create_mock_actor(MockTestActor, 'test')
        state_manager = mock_actor._state_manager
        with self.assertRaises(KeyError):
            await state_manager.get_state('state')
        await state_manager.add_state('state', 5)
        value = await state_manager.get_state('state')
        self.assertIs(value, 5)

    async def test_set_state(self):
        mock_actor = create_mock_actor(MockTestActor, 'test')
        state_manager = mock_actor._state_manager
        await state_manager.set_state('state', 5)
        self.assertIs(state_manager._mock_state['state'], 5)
        await state_manager.set_state('state', 10)
        self.assertIs(state_manager._mock_state['state'], 10)

    async def test_remove_state(self):
        mock_actor = create_mock_actor(MockTestActor, 'test')
        state_manager = mock_actor._state_manager
        await state_manager.set_state('state', 5)
        self.assertIs(state_manager._mock_state['state'], 5)
        await state_manager.remove_state('state')
        self.assertFalse(state_manager._mock_state)
        with self.assertRaises(KeyError):
            await state_manager.remove_state('state')

    async def test_contains_state(self):
        mock_actor = create_mock_actor(MockTestActor, 'test')
        state_manager = mock_actor._state_manager
        self.assertFalse(await state_manager.contains_state('state'))
        await state_manager.set_state('state', 5)
        self.assertTrue(await state_manager.contains_state('state'))
        await state_manager.remove_state('state')
        self.assertFalse(await state_manager.contains_state('state'))

    async def test_get_or_add_state(self):
        mock_actor = create_mock_actor(MockTestActor, 'test')
        state_manager = mock_actor._state_manager
        out = await state_manager.get_or_add_state('state', 5)
        self.assertIs(out, 5)
        self.assertIs(state_manager._mock_state['state'], 5)
        out = await state_manager.get_or_add_state('state', 10)
        self.assertIs(out, 5)
        self.assertIs(state_manager._mock_state['state'], 5)

    async def test_add_or_update_state(self):
        mock_actor = create_mock_actor(MockTestActor, 'test')
        state_manager = mock_actor._state_manager
        await state_manager.add_or_update_state('state', 5, double)
        self.assertIs(state_manager._mock_state['state'], 5)
        await state_manager.add_or_update_state('state', 1000, double)
        self.assertIs(state_manager._mock_state['state'], 10)

    async def test_get_state_names(self):
        mock_actor = create_mock_actor(MockTestActor, 'test')
        state_manager = mock_actor._state_manager
        names = await state_manager.get_state_names()
        self.assertFalse(names)
        await state_manager.set_state('state1', 5)
        names = await state_manager.get_state_names()
        self.assertCountEqual(names, ['state1'])
        await state_manager.set_state('state2', 5)
        names = await state_manager.get_state_names()
        self.assertCountEqual(names, ['state1', 'state2'])
        await state_manager.save_state()
        names = await state_manager.get_state_names()
        self.assertFalse(names)

    async def test_clear_cache(self):
        mock_actor = create_mock_actor(MockTestActor, 'test')
        state_manager = mock_actor._state_manager
        self.assertFalse(state_manager._default_state_change_tracker)
        await state_manager.set_state('state1', 5)
        self.assertTrue('state1', state_manager._default_state_change_tracker)
        await state_manager.clear_cache()
        self.assertFalse(state_manager._default_state_change_tracker)
