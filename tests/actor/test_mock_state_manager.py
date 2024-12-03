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

    async def test_state_methods(self):
        mock_actor = create_mock_actor(MockTestActor, 'test')
        state_manager = mock_actor._state_manager
        self.assertFalse(await state_manager.contains_state('state'))
        self.assertFalse(state_manager._default_state_change_tracker)
        names = await state_manager.get_state_names()
        self.assertFalse(names)
        with self.assertRaises(KeyError):
            await state_manager.get_state('state')
        await state_manager.add_state('state', 5)
        names = await state_manager.get_state_names()
        self.assertCountEqual(names, ['state'])
        self.assertIs(state_manager._mock_state['state'], 5)
        value = await state_manager.get_state('state')
        self.assertIs(value, 5)
        await state_manager.add_state('state2', 5)
        self.assertIs(state_manager._mock_state['state2'], 5)
        with self.assertRaises(ValueError):
            await state_manager.add_state('state', 5)
        await state_manager.set_state('state3', 5)
        self.assertIs(state_manager._mock_state['state3'], 5)
        await state_manager.set_state('state3', 10)
        self.assertIs(state_manager._mock_state['state3'], 10)
        self.assertTrue(await state_manager.contains_state('state3'))
        await state_manager.remove_state('state3')
        self.assertFalse('state3' in state_manager._mock_state)
        with self.assertRaises(KeyError):
            await state_manager.remove_state('state3')
        self.assertFalse(await state_manager.contains_state('state3'))
        await state_manager.add_or_update_state('state3', 5, double)
        self.assertIs(state_manager._mock_state['state3'], 5)
        await state_manager.add_or_update_state('state3', 1000, double)
        self.assertIs(state_manager._mock_state['state3'], 10)
        out = await state_manager.get_or_add_state('state4', 5)
        self.assertIs(out, 5)
        self.assertIs(state_manager._mock_state['state4'], 5)
        out = await state_manager.get_or_add_state('state4', 10)
        self.assertIs(out, 5)
        self.assertIs(state_manager._mock_state['state4'], 5)
        names = await state_manager.get_state_names()
        self.assertCountEqual(names, ['state', 'state2', 'state3', 'state4'])
        self.assertTrue('state', state_manager._default_state_change_tracker)
        await state_manager.clear_cache()
        self.assertFalse(state_manager._default_state_change_tracker)
