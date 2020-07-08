# -*- coding: utf-8 -*-

"""
Copyright (c) Microsoft Corporation.
Licensed under the MIT License.
"""

import unittest
import asyncio

from unittest import mock
from datetime import timedelta

from dapr.actor.id import ActorId
from dapr.actor.runtime.config import ActorRuntimeConfig
from dapr.actor.runtime.context import ActorRuntimeContext
from dapr.actor.runtime.runtime import ActorRuntime
from dapr.actor.runtime._type_information import ActorTypeInformation
from dapr.serializers import DefaultJSONSerializer

from tests.actor.fake_actor_classes import (
    FakeDaprActorClient,
    FakeSimpleActor,
    FakeSimpleReminderActor,
    FakeSimpleTimerActor,
    FakeMultiInterfacesActor,
)

def async_mock(*args, **kwargs):
    m = mock.MagicMock(*args, **kwargs)

    async def mock_coro(*args, **kwargs):
        return m(*args, **kwargs)

    mock_coro.mock = m
    return mock_coro

def _run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)

class ActorTests(unittest.TestCase):
    def setUp(self):
        ActorRuntime._actor_managers = {}
        ActorRuntime.set_actor_config(ActorRuntimeConfig())
        self._serializer = DefaultJSONSerializer()
        _run(ActorRuntime.register_actor(FakeSimpleActor))
        _run(ActorRuntime.register_actor(FakeMultiInterfacesActor))

    def test_get_registered_actor_types(self):
        actor_types = ActorRuntime.get_registered_actor_types()
        self.assertTrue(actor_types.index('FakeSimpleActor') >= 0)
        self.assertTrue(actor_types.index(FakeMultiInterfacesActor.__name__) >= 0)

    def test_actor_config(self):
        config = ActorRuntime.get_actor_config()

        self.assertTrue(config._drain_rebalanced_actors)
        self.assertEqual(timedelta(hours=1), config._actor_idle_timeout)
        self.assertEqual(timedelta(seconds=30), config._actor_scan_interval)
        self.assertEqual(timedelta(minutes=1), config._drain_ongoing_call_timeout)
        self.assertEqual(2, len(config._entities))

        # apply new config
        new_config = ActorRuntimeConfig(
            timedelta(hours=3), timedelta(seconds=10), timedelta(minutes=1), False)

        ActorRuntime.set_actor_config(new_config)
        config = ActorRuntime.get_actor_config()

        self.assertFalse(config._drain_rebalanced_actors)
        self.assertEqual(timedelta(hours=3), config._actor_idle_timeout)
        self.assertEqual(timedelta(seconds=10), config._actor_scan_interval)
        self.assertEqual(timedelta(minutes=1), config._drain_ongoing_call_timeout)
        self.assertEqual(2, len(config._entities))

    def test_entities_update(self):
        # Clean up managers
        ActorRuntime._actor_managers = {}
        ActorRuntime.set_actor_config(ActorRuntimeConfig())

        config = ActorRuntime.get_actor_config()
        with self.assertRaises(ValueError):
            config._entities.index(FakeSimpleActor.__name__)

        _run(ActorRuntime.register_actor(FakeSimpleActor))
        config = ActorRuntime.get_actor_config()
        self.assertTrue(config._entities.index(FakeSimpleActor.__name__) >= 0)

    def test_dispatch(self):
        _run(ActorRuntime.register_actor(FakeMultiInterfacesActor))

        request_body = {
            "message": "hello dapr",
        }

        test_request_body = self._serializer.serialize(request_body)
        response = _run(ActorRuntime.dispatch(
            FakeMultiInterfacesActor.__name__, 'test-id',
            "ActionMethod", test_request_body))

        self.assertEqual(b'"hello dapr"', response)

        _run(ActorRuntime.deactivate(FakeMultiInterfacesActor.__name__, 'test-id'))

        # Ensure test-id is deactivated
        with self.assertRaises(ValueError):
            _run(ActorRuntime.deactivate(FakeMultiInterfacesActor.__name__, 'test-id'))

    @mock.patch('FakeDaprActorClient.register_reminder', new=async_mock(return_value=b'"ok"'))
    @mock.patch('FakeDaprActorClient.unregister_reminder', new=async_mock(return_value=b'"ok"'))
    def test_register_reminder(self):

        test_actor_id = ActorId('test_id')
        test_type_info = ActorTypeInformation.create(FakeSimpleReminderActor)
        test_client = FakeDaprActorClient
        ctx = ActorRuntimeContext(
            test_type_info, self._serializer,
            self._serializer, test_client)
        test_actor = FakeSimpleReminderActor(ctx, test_actor_id)

        # register reminder
        _run(test_actor.register_reminder(
            'test_reminder', b'reminder_message',
            timedelta(seconds=1), timedelta(seconds=1)))
        test_client.register_reminder.mock.assert_called_once()
        test_client.register_reminder.mock.assert_called_with(
            'FakeSimpleReminderActor', 'test_id',
            'test_reminder',
            b'{"name":"test_reminder","dueTime":"0h0m1s","period":"0h0m1s","data":"cmVtaW5kZXJfbWVzc2FnZQ=="}')  # noqa E501

        # unregister reminder
        _run(test_actor.unregister_reminder('test_reminder'))
        test_client.unregister_reminder.mock.assert_called_once()
        test_client.unregister_reminder.mock.assert_called_with(
            'FakeSimpleReminderActor', 'test_id', 'test_reminder')

    @mock.patch('FakeDaprActorClient.register_timer', new=async_mock(return_value=b'"ok"'))
    @mock.patch('FakeDaprActorClient.unregister_timer', new=async_mock(return_value=b'"ok"'))
    def test_register_timer(self):

        test_actor_id = ActorId('test_id')
        test_type_info = ActorTypeInformation.create(FakeSimpleTimerActor)
        test_client = FakeDaprActorClient
        ctx = ActorRuntimeContext(
            test_type_info, self._serializer,
            self._serializer, test_client)
        test_actor = FakeSimpleTimerActor(ctx, test_actor_id)

        # register timer
        _run(test_actor.register_timer(
            'test_timer', test_actor.timer_callback,
            "timer call", timedelta(seconds=1), timedelta(seconds=1)))
        test_client.mock.register_timer.assert_called_once()
        test_client.mock.register_timer.assert_called_with(
            'FakeSimpleTimerActor', 'test_id', 'test_timer',
            b'{"dueTime":"0h0m1s","period":"0h0m1s"}')
        self.assertTrue('test_timer' in test_actor._timers)
        self.assertEqual(1, len(test_actor._timers))

        # unregister timer
        _run(test_actor.unregister_timer('test_timer'))
        test_client.mock.unregister_timer.assert_called_once()
        test_client.mock.unregister_timer.assert_called_with(
            'FakeSimpleTimerActor', 'test_id', 'test_timer')
        self.assertEqual(0, len(test_actor._timers))

        # register timer without timer name
        _run(test_actor.register_timer(
            None, test_actor.timer_callback,
            "timer call", timedelta(seconds=1), timedelta(seconds=1)))
        self.assertEqual("test_id_Timer_1", list(test_actor._timers)[0])
