# -*- coding: utf-8 -*-

"""
Copyright (c) Microsoft Corporation.
Licensed under the MIT License.
"""

import base64
import unittest

from unittest import mock

from dapr.actor.id import ActorId
from dapr.actor.runtime.context import ActorRuntimeContext
from dapr.actor.runtime.state_change import StateChangeKind
from dapr.actor.runtime.state_manager import ActorStateManager
from dapr.actor.runtime._type_information import ActorTypeInformation
from dapr.serializers import DefaultJSONSerializer

from tests.actor.fake_actor_classes import FakeSimpleActor
from tests.actor.fake_client import FakeDaprActorClient

from tests.actor.utils import (
    _async_mock,
    _run
)


class ActorStateManagerTests(unittest.TestCase):
    def setUp(self):
        # Create mock client
        self._fake_client = FakeDaprActorClient

        self._test_actor_id = ActorId('1')
        self._test_type_info = ActorTypeInformation.create(FakeSimpleActor)
        self._serializer = DefaultJSONSerializer()
        self._runtime_ctx = ActorRuntimeContext(
            self._test_type_info, self._serializer, self._serializer, self._fake_client)
        self._fake_actor = FakeSimpleActor(self._runtime_ctx, self._test_actor_id)

    @mock.patch(
        'tests.actor.fake_client.FakeDaprActorClient.get_state',
        new=_async_mock(return_value=base64.b64encode(b'"value1"')))
    @mock.patch(
        'tests.actor.fake_client.FakeDaprActorClient.save_state_transactionally',
        new=_async_mock())
    def test_add_state(self):

        state_manager = ActorStateManager(self._fake_actor)

        # Add first 'state1'
        added = _run(state_manager.try_add_state('state1', 'value1'))
        self.assertTrue(added)

        state = state_manager._state_change_tracker['state1']
        self.assertEqual('value1', state.value)
        self.assertEqual(StateChangeKind.add, state.change_kind)

        # Add 'state1' again
        added = _run(state_manager.try_add_state('state1', 'value1'))
        self.assertFalse(added)

    @mock.patch('tests.actor.fake_client.FakeDaprActorClient.get_state', new=_async_mock())
    def test_get_state_for_no_state(self):

        state_manager = ActorStateManager(self._fake_actor)
        has_value, val = _run(state_manager.try_get_state('state1'))
        self.assertFalse(has_value)
        self.assertIsNone(val)

        # Test if the test value is empty string
        self._fake_client.get_state.return_value = ''
        has_value, val = _run(state_manager.try_get_state('state1'))
        self.assertFalse(has_value)
        self.assertIsNone(val)

    @mock.patch(
        'tests.actor.fake_client.FakeDaprActorClient.get_state',
        new=_async_mock(return_value=b'"value1"'))
    def test_get_state_for_existing_value(self):

        state_manager = ActorStateManager(self._fake_actor)
        has_value, val = _run(state_manager.try_get_state('state1'))
        self.assertTrue(has_value)
        self.assertEqual("value1", val)

    @mock.patch(
        'tests.actor.fake_client.FakeDaprActorClient.get_state',
        new=_async_mock(return_value=b'"value1"'))
    def test_get_state_for_removed_value(self):

        state_manager = ActorStateManager(self._fake_actor)
        removed = _run(state_manager.try_remove_state('state1'))
        self.assertTrue(removed)

        state = state_manager._state_change_tracker['state1']
        self.assertEqual(StateChangeKind.remove, state.change_kind)

        has_value, val = _run(state_manager.try_get_state('state1'))
        self.assertFalse(has_value)
        self.assertIsNone(val)

    @mock.patch('tests.actor.fake_client.FakeDaprActorClient.get_state', new=_async_mock())
    def test_set_state_for_new_state(self):

        state_manager = ActorStateManager(self._fake_actor)
        _run(state_manager.set_state('state1', 'value1'))

        state = state_manager._state_change_tracker['state1']
        self.assertEqual(StateChangeKind.add, state.change_kind)
        self.assertEqual('value1', state.value)

    @mock.patch('tests.actor.fake_client.FakeDaprActorClient.get_state', new=_async_mock())
    def test_set_state_for_existing_state_only_in_mem(self):

        state_manager = ActorStateManager(self._fake_actor)
        _run(state_manager.set_state('state1', 'value1'))

        state = state_manager._state_change_tracker['state1']
        self.assertEqual(StateChangeKind.add, state.change_kind)
        self.assertEqual('value1', state.value)

        _run(state_manager.set_state('state1', 'value2'))
        state = state_manager._state_change_tracker['state1']
        self.assertEqual(StateChangeKind.add, state.change_kind)
        self.assertEqual('value2', state.value)

    @mock.patch(
        'tests.actor.fake_client.FakeDaprActorClient.get_state',
        new=_async_mock(return_value=b'"value1"'))
    def test_set_state_for_existing_state(self):

        state_manager = ActorStateManager(self._fake_actor)
        _run(state_manager.set_state('state1', 'value2'))
        state = state_manager._state_change_tracker['state1']
        self.assertEqual(StateChangeKind.update, state.change_kind)
        self.assertEqual('value2', state.value)

    @mock.patch('tests.actor.fake_client.FakeDaprActorClient.get_state', new=_async_mock())
    def test_remove_state_for_non_existing_state(self):

        state_manager = ActorStateManager(self._fake_actor)
        removed = _run(state_manager.try_remove_state('state1'))
        self.assertFalse(removed)

    @mock.patch(
        'tests.actor.fake_client.FakeDaprActorClient.get_state',
        new=_async_mock(return_value=b'"value1"'))
    def test_remove_state_for_existing_state(self):

        state_manager = ActorStateManager(self._fake_actor)
        removed = _run(state_manager.try_remove_state('state1'))
        self.assertTrue(removed)

        state = state_manager._state_change_tracker['state1']
        self.assertEqual(StateChangeKind.remove, state.change_kind)

    @mock.patch('tests.actor.fake_client.FakeDaprActorClient.get_state', new=_async_mock())
    def test_remove_state_for_existing_state_in_mem(self):

        state_manager = ActorStateManager(self._fake_actor)
        _run(state_manager.set_state('state1', 'value1'))
        removed = _run(state_manager.try_remove_state('state1'))
        self.assertTrue(removed)

    @mock.patch('tests.actor.fake_client.FakeDaprActorClient.get_state', new=_async_mock())
    def test_remove_state_twice_for_existing_state_in_mem(self):

        state_manager = ActorStateManager(self._fake_actor)
        _run(state_manager.set_state('state1', 'value1'))
        removed = _run(state_manager.try_remove_state('state1'))
        self.assertTrue(removed)
        removed = _run(state_manager.try_remove_state('state1'))
        self.assertFalse(removed)

    @mock.patch('tests.actor.fake_client.FakeDaprActorClient.get_state', new=_async_mock())
    def test_contains_state_for_removed_state(self):

        state_manager = ActorStateManager(self._fake_actor)
        _run(state_manager.set_state('state1', 'value1'))

        exist = _run(state_manager.contains_state('state1'))
        self.assertTrue(exist)

    @mock.patch(
        'tests.actor.fake_client.FakeDaprActorClient.get_state',
        new=_async_mock(return_value=b'"value1"'))
    def test_contains_state_for_existing_state(self):

        state_manager = ActorStateManager(self._fake_actor)
        exist = _run(state_manager.contains_state('state1'))
        self.assertTrue(exist)

    @mock.patch(
        'tests.actor.fake_client.FakeDaprActorClient.get_state',
        new=_async_mock(return_value=b'"value1"'))
    def test_get_or_add_state_for_existing_state(self):

        state_manager = ActorStateManager(self._fake_actor)
        val = _run(state_manager.get_or_add_state('state1', 'value2'))
        self.assertEqual('value1', val)

    @mock.patch(
        'tests.actor.fake_client.FakeDaprActorClient.get_state',
        new=_async_mock())
    def test_get_or_add_state_for_non_existing_state(self):
        state_manager = ActorStateManager(self._fake_actor)
        val = _run(state_manager.get_or_add_state('state1', 'value2'))

        state = state_manager._state_change_tracker['state1']
        self.assertEqual(StateChangeKind.add, state.change_kind)
        self.assertEqual('value2', val)

        self._fake_client.get_state.mock.assert_called_once_with(
            self._test_type_info._name,
            self._test_actor_id.id, 'state1')

    @mock.patch(
        'tests.actor.fake_client.FakeDaprActorClient.get_state',
        new=_async_mock(return_value=b'"value1"'))
    def test_get_or_add_state_for_removed_state(self):

        state_manager = ActorStateManager(self._fake_actor)
        _run(state_manager.remove_state('state1'))
        state = state_manager._state_change_tracker['state1']
        self.assertEqual(StateChangeKind.remove, state.change_kind)

        val = _run(state_manager.get_or_add_state('state1', 'value2'))
        state = state_manager._state_change_tracker['state1']
        self.assertEqual(StateChangeKind.update, state.change_kind)
        self.assertEqual('value2', val)

    @mock.patch('tests.actor.fake_client.FakeDaprActorClient.get_state', new=_async_mock())
    def test_add_or_update_state_for_new_state(self):
        """adds state if state does not exist."""
        def test_update_value(name, value):
            return f'{name}-{value}'

        state_manager = ActorStateManager(self._fake_actor)
        val = _run(state_manager.add_or_update_state('state1', 'value1', test_update_value))
        self.assertEqual('value1', val)
        state = state_manager._state_change_tracker['state1']
        self.assertEqual(StateChangeKind.add, state.change_kind)

    @mock.patch(
        'tests.actor.fake_client.FakeDaprActorClient.get_state',
        new=_async_mock(return_value=b'"value1"'))
    def test_add_or_update_state_for_state_in_storage(self):
        """updates state value using update_value_factory if state is
        in the storage."""
        def test_update_value(name, value):
            return f'{name}-{value}'

        state_manager = ActorStateManager(self._fake_actor)
        val = _run(state_manager.add_or_update_state('state1', 'value1', test_update_value))
        self.assertEqual('state1-value1', val)
        state = state_manager._state_change_tracker['state1']
        self.assertEqual(StateChangeKind.update, state.change_kind)

    @mock.patch(
        'tests.actor.fake_client.FakeDaprActorClient.get_state',
        new=_async_mock(return_value=b'"value1"'))
    def test_add_or_update_state_for_removed_state(self):
        """add state value if state was removed."""
        def test_update_value(name, value):
            return f'{name}-{value}'

        state_manager = ActorStateManager(self._fake_actor)
        _run(state_manager.remove_state('state1'))

        val = _run(state_manager.add_or_update_state('state1', 'value1', test_update_value))
        self.assertEqual('value1', val)

    @mock.patch(
        'tests.actor.fake_client.FakeDaprActorClient.get_state',
        new=_async_mock(return_value=b'"value1"'))
    def test_add_or_update_state_for_none_state_key(self):
        """update state value for StateChangeKind.none state """
        def test_update_value(name, value):
            return f'{name}-{value}'

        state_manager = ActorStateManager(self._fake_actor)
        has_value, val = _run(state_manager.try_get_state('state1'))
        self.assertTrue(has_value)
        self.assertEqual('value1', val)

        val = _run(state_manager.add_or_update_state('state1', 'value1', test_update_value))
        self.assertEqual('state1-value1', val)

    def test_add_or_update_state_without_update_value_factory(self):
        """tries to add or update state without update_value_factory """
        state_manager = ActorStateManager(self._fake_actor)
        with self.assertRaises(AttributeError):
            _run(state_manager.add_or_update_state('state1', 'value1', None))

    @mock.patch('tests.actor.fake_client.FakeDaprActorClient.get_state', new=_async_mock())
    def test_get_state_names(self):
        state_manager = ActorStateManager(self._fake_actor)
        _run(state_manager.set_state('state1', 'value1'))
        _run(state_manager.set_state('state2', 'value2'))
        _run(state_manager.set_state('state3', 'value3'))
        names = _run(state_manager.get_state_names())
        self.assertEqual(['state1', 'state2', 'state3'], names)

        self._fake_client.get_state.mock.assert_any_call(
            self._test_type_info._name,
            self._test_actor_id.id,
            'state1')
        self._fake_client.get_state.mock.assert_any_call(
            self._test_type_info._name,
            self._test_actor_id.id,
            'state2')
        self._fake_client.get_state.mock.assert_any_call(
            self._test_type_info._name,
            self._test_actor_id.id,
            'state3')

    @mock.patch(
        'tests.actor.fake_client.FakeDaprActorClient.get_state',
        new=_async_mock(return_value=b'"value0"'))
    def test_clear_cache(self):
        state_manager = ActorStateManager(self._fake_actor)
        _run(state_manager.set_state('state1', 'value1'))
        _run(state_manager.set_state('state2', 'value2'))
        _run(state_manager.set_state('state3', 'value3'))
        _run(state_manager.clear_cache())

        self.assertEqual(0, len(state_manager._state_change_tracker))

    @mock.patch(
        'tests.actor.fake_client.FakeDaprActorClient.get_state',
        new=_async_mock(return_value=b'"value3"'))
    @mock.patch(
        'tests.actor.fake_client.FakeDaprActorClient.save_state_transactionally',
        new=_async_mock())
    def test_save_state(self):
        state_manager = ActorStateManager(self._fake_actor)
        # set states which are StateChangeKind.add
        _run(state_manager.set_state('state1', 'value1'))
        _run(state_manager.set_state('state2', 'value2'))

        has_value, val = _run(state_manager.try_get_state('state3'))
        self.assertTrue(has_value)
        self.assertEqual("value3", val)
        # set state which is StateChangeKind.remove
        _run(state_manager.remove_state('state4'))
        # set state which is StateChangeKind.update
        _run(state_manager.set_state('state5', 'value5'))
        expected = b'[{"operation":"upsert","request":{"key":"state1","value":"value1"}},{"operation":"upsert","request":{"key":"state2","value":"value2"}},{"operation":"delete","request":{"key":"state4"}},{"operation":"upsert","request":{"key":"state5","value":"value5"}}]'  # noqa: E501

        # Save the state
        def mock_save_state(actor_type, actor_id, data):
            self.assertEqual(expected, data)

        self._fake_client.save_state_transactionally.mock = mock_save_state
        _run(state_manager.save_state())


if __name__ == '__main__':
    unittest.main()
