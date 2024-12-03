import unittest
from dapr.actor.runtime.state_manager import StateChangeKind
from dapr.actor.runtime.mock_state_manager import MockStateManager
from dapr.actor.runtime.mock_actor import MockActor


class TestMockStateManager(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        """Set up a mock actor and state manager."""

        class TestActor(MockActor):
            pass

        self.mock_actor = TestActor(actor_id='test_actor', initstate=None)
        self.state_manager = MockStateManager(
            actor=self.mock_actor, initstate={'initial_key': 'initial_value'}
        )

    async def test_add_state(self):
        """Test adding a new state."""
        await self.state_manager.add_state('new_key', 'new_value')
        state = await self.state_manager.get_state('new_key')
        self.assertEqual(state, 'new_value')

        # Ensure it is tracked as an added state
        tracker = self.state_manager._default_state_change_tracker
        self.assertEqual(tracker['new_key'].change_kind, StateChangeKind.add)
        self.assertEqual(tracker['new_key'].value, 'new_value')

    async def test_get_existing_state(self):
        """Test retrieving an existing state."""
        state = await self.state_manager.get_state('initial_key')
        self.assertEqual(state, 'initial_value')

    async def test_get_nonexistent_state(self):
        """Test retrieving a state that does not exist."""
        with self.assertRaises(KeyError):
            await self.state_manager.get_state('nonexistent_key')

    async def test_update_state(self):
        """Test updating an existing state."""
        await self.state_manager.set_state('initial_key', 'updated_value')
        state = await self.state_manager.get_state('initial_key')
        self.assertEqual(state, 'updated_value')

        # Ensure it is tracked as an updated state
        tracker = self.state_manager._default_state_change_tracker
        self.assertEqual(tracker['initial_key'].change_kind, StateChangeKind.update)
        self.assertEqual(tracker['initial_key'].value, 'updated_value')

    async def test_remove_state(self):
        """Test removing an existing state."""
        await self.state_manager.remove_state('initial_key')
        with self.assertRaises(KeyError):
            await self.state_manager.get_state('initial_key')

        # Ensure it is tracked as a removed state
        tracker = self.state_manager._default_state_change_tracker
        self.assertEqual(tracker['initial_key'].change_kind, StateChangeKind.remove)

    async def test_save_state(self):
        """Test saving state changes."""
        await self.state_manager.add_state('key1', 'value1')
        await self.state_manager.set_state('initial_key', 'value2')
        await self.state_manager.remove_state('initial_key')

        await self.state_manager.save_state()

        # After saving, state tracker should be cleared
        tracker = self.state_manager._default_state_change_tracker
        self.assertEqual(len(tracker), 1)

        # State changes should be reflected in _mock_state
        self.assertIn('key1', self.state_manager._mock_state)
        self.assertEqual(self.state_manager._mock_state['key1'], 'value1')
        self.assertNotIn('initial_key', self.state_manager._mock_state)

    async def test_contains_state(self):
        """Test checking if a state exists."""
        self.assertTrue(await self.state_manager.contains_state('initial_key'))
        self.assertFalse(await self.state_manager.contains_state('nonexistent_key'))

    async def test_clear_cache(self):
        """Test clearing the cache."""
        await self.state_manager.add_state('key1', 'value1')
        await self.state_manager.clear_cache()

        # Tracker should be empty
        self.assertEqual(len(self.state_manager._default_state_change_tracker), 0)

    async def test_state_ttl(self):
        """Test setting state with TTL."""
        await self.state_manager.set_state_ttl('key_with_ttl', 'value', ttl_in_seconds=10)
        tracker = self.state_manager._default_state_change_tracker
        self.assertEqual(tracker['key_with_ttl'].ttl_in_seconds, 10)


if __name__ == '__main__':
    unittest.main()
