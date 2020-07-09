# -*- coding: utf-8 -*-

"""
Copyright (c) Microsoft Corporation.
Licensed under the MIT License.
"""

import unittest

from datetime import timedelta
from unittest.mock import AsyncMock

from dapr.actor.id import ActorId
from dapr.actor.runtime.config import ActorRuntimeConfig
from dapr.actor.runtime.context import ActorRuntimeContext
from dapr.actor.runtime.runtime import ActorRuntime
from dapr.actor.runtime._type_information import ActorTypeInformation
from dapr.serializers import DefaultJSONSerializer

from tests.actor.fake_actor_classes import (
    FakeSimpleActor,
    FakeSimpleReminderActor,
    FakeSimpleTimerActor,
    FakeMultiInterfacesActor,
)


class ActorTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        ActorRuntime._actor_managers = {}
        ActorRuntime.set_actor_config(ActorRuntimeConfig())
        self._serializer = DefaultJSONSerializer()
        await ActorRuntime.register_actor(FakeSimpleActor)
        await ActorRuntime.register_actor(FakeMultiInterfacesActor)

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

    async def test_entities_update(self):
        # Clean up managers
        ActorRuntime._actor_managers = {}
        ActorRuntime.set_actor_config(ActorRuntimeConfig())

        config = ActorRuntime.get_actor_config()
        with self.assertRaises(ValueError):
            config._entities.index(FakeSimpleActor.__name__)

        await ActorRuntime.register_actor(FakeSimpleActor)
        config = ActorRuntime.get_actor_config()
        self.assertTrue(config._entities.index(FakeSimpleActor.__name__) >= 0)

    async def test_dispatch(self):
        await ActorRuntime.register_actor(FakeMultiInterfacesActor)

        request_body = {
            "message": "hello dapr",
        }

        test_request_body = self._serializer.serialize(request_body)
        response = await ActorRuntime.dispatch(
            FakeMultiInterfacesActor.__name__, 'test-id',
            "ActionMethod", test_request_body)

        self.assertEqual(b'"hello dapr"', response)

        await ActorRuntime.deactivate(FakeMultiInterfacesActor.__name__, 'test-id')

        # Ensure test-id is deactivated
        with self.assertRaises(ValueError):
            await ActorRuntime.deactivate(FakeMultiInterfacesActor.__name__, 'test-id')

    async def test_register_reminder(self):
        fake_client = AsyncMock()
        fake_client.register_reminder.return_value = b'"ok"'
        fake_client.unregister_reminder.return_value = b'"ok"'

        test_actor_id = ActorId('test_id')
        test_type_info = ActorTypeInformation.create(FakeSimpleReminderActor)
        ctx = ActorRuntimeContext(
            test_type_info, self._serializer,
            self._serializer, fake_client)
        test_actor = FakeSimpleReminderActor(ctx, test_actor_id)

        # register reminder
        await test_actor.register_reminder(
            'test_reminder', b'reminder_message',
            timedelta(seconds=1), timedelta(seconds=1))
        fake_client.register_reminder.assert_called_once()
        fake_client.register_reminder.assert_called_with(
            'FakeSimpleReminderActor', 'test_id',
            'test_reminder',
            b'{"name":"test_reminder","dueTime":"0h0m1s","period":"0h0m1s","data":"cmVtaW5kZXJfbWVzc2FnZQ=="}')  # noqa E501

        # unregister reminder
        await test_actor.unregister_reminder('test_reminder')
        fake_client.unregister_reminder.assert_called_once()
        fake_client.unregister_reminder.assert_called_with(
            'FakeSimpleReminderActor', 'test_id', 'test_reminder')

    async def test_register_timer(self):
        fake_client = AsyncMock()
        fake_client.register_timer.return_value = b'"ok"'
        fake_client.unregister_timer.return_value = b'"ok"'

        test_actor_id = ActorId('test_id')
        test_type_info = ActorTypeInformation.create(FakeSimpleTimerActor)
        ctx = ActorRuntimeContext(
            test_type_info, self._serializer,
            self._serializer, fake_client)
        test_actor = FakeSimpleTimerActor(ctx, test_actor_id)

        # register timer
        await test_actor.register_timer(
            'test_timer', test_actor.timer_callback,
            "timer call", timedelta(seconds=1), timedelta(seconds=1))
        fake_client.register_timer.assert_called_once()
        fake_client.register_timer.assert_called_with(
            'FakeSimpleTimerActor', 'test_id', 'test_timer',
            b'{"dueTime":"0h0m1s","period":"0h0m1s"}')
        self.assertTrue('test_timer' in test_actor._timers)
        self.assertEqual(1, len(test_actor._timers))

        # unregister timer
        await test_actor.unregister_timer('test_timer')
        fake_client.unregister_timer.assert_called_once()
        fake_client.unregister_timer.assert_called_with(
            'FakeSimpleTimerActor', 'test_id', 'test_timer')
        self.assertEqual(0, len(test_actor._timers))

        # register timer without timer name
        await test_actor.register_timer(
            None, test_actor.timer_callback,
            "timer call", timedelta(seconds=1), timedelta(seconds=1))
        self.assertEqual("test_id_Timer_1", list(test_actor._timers)[0])
