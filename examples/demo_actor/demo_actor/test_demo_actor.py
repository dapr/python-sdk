import unittest

from demo_actor import DemoActor

from dapr.actor.runtime.mock_actor import create_mock_actor


class DemoActorTests(unittest.IsolatedAsyncioTestCase):
    def test_create_actor(self):
        mockactor = create_mock_actor(DemoActor, '1')
        self.assertEqual(mockactor.id.id, '1')

    async def test_get_data(self):
        mockactor = create_mock_actor(DemoActor, '1')
        self.assertFalse(mockactor._state_manager._mock_state)
        val = await mockactor.get_my_data()
        self.assertIsNone(val)

    async def test_set_data(self):
        mockactor = create_mock_actor(DemoActor, '1')
        await mockactor.set_my_data({'state': 5})
        val = await mockactor.get_my_data()
        self.assertIs(val['state'], 5)  # type: ignore

    async def test_clear_data(self):
        mockactor = create_mock_actor(DemoActor, '1')
        await mockactor.set_my_data({'state': 5})
        val = await mockactor.get_my_data()
        self.assertIs(val['state'], 5)  # type: ignore
        await mockactor.clear_my_data()
        val = await mockactor.get_my_data()
        self.assertIsNone(val)

    async def test_reminder(self):
        mockactor = create_mock_actor(DemoActor, '1')
        self.assertFalse(mockactor._state_manager._mock_reminders)
        await mockactor.set_reminder(True)
        self.assertTrue('demo_reminder' in mockactor._state_manager._mock_reminders)
        await mockactor.set_reminder(False)
        self.assertFalse(mockactor._state_manager._mock_reminders)
