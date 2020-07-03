# -*- coding: utf-8 -*-

"""
Copyright (c) Microsoft Corporation.
Licensed under the MIT License.
"""

import unittest
from datetime import timedelta
from unittest.mock import AsyncMock

from dapr.actor.id import ActorId
from dapr.actor.runtime._type_information import ActorTypeInformation
from dapr.actor.runtime.manager import ActorManager
from dapr.actor.runtime.context import ActorRuntimeContext
from dapr.serializers import DefaultJSONSerializer

from tests.actor.fake_actor_classes import (
    FakeMultiInterfacesActor,
    FakeSimpleActor,
    FakeSimpleReminderActor,
    FakeSimpleTimerActor,
)


class ActorManagerTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self._test_type_info = ActorTypeInformation.create(FakeMultiInterfacesActor)
        self._serializer = DefaultJSONSerializer()

        self._fake_client = AsyncMock()
        self._fake_client.invoke_method.return_value = b'"expected_response"'
        self._runtime_ctx = ActorRuntimeContext(
            self._test_type_info, self._serializer,
            self._serializer, self._fake_client)
        self._manager = ActorManager(self._runtime_ctx)

    async def test_activate_actor(self):
        """Activate ActorId(1)"""
        test_actor_id = ActorId('1')
        await self._manager.activate_actor(test_actor_id)

        # assert
        self.assertEqual(test_actor_id, self._manager._active_actors[test_actor_id.id].id)
        self.assertTrue(self._manager._active_actors[test_actor_id.id].activated)
        self.assertFalse(self._manager._active_actors[test_actor_id.id].deactivated)

    async def test_deactivate_actor(self):
        """Activate ActorId('2') and deactivate it"""
        test_actor_id = ActorId('2')
        await self._manager.activate_actor(test_actor_id)

        # assert
        self.assertEqual(test_actor_id, self._manager._active_actors[test_actor_id.id].id)
        self.assertTrue(self._manager._active_actors[test_actor_id.id].activated)
        self.assertFalse(self._manager._active_actors[test_actor_id.id].deactivated)

        await self._manager.deactivate_actor(test_actor_id)
        self.assertIsNone(self._manager._active_actors.get(test_actor_id.id))

    async def test_dispatch_success(self):
        """dispatch ActionMethod"""
        test_actor_id = ActorId('dispatch')
        await self._manager.activate_actor(test_actor_id)

        request_body = {
            "message": "hello dapr",
        }

        test_request_body = self._serializer.serialize(request_body)
        response = await self._manager.dispatch(test_actor_id, "ActionMethod", test_request_body)
        self.assertEqual(b'"hello dapr"', response)


class ActorManagerReminderTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self._serializer = DefaultJSONSerializer()
        self._fake_client = AsyncMock()
        self._fake_client.invoke_method.return_value = b'"expected_response"'

        self._test_reminder_req = self._serializer.serialize({
            'name': 'test_reminder',
            'dueTime': timedelta(seconds=1),
            'period': timedelta(seconds=1),
            'data': 'cmVtaW5kZXJfc3RhdGU=',
        })

    async def test_fire_reminder_for_non_reminderable(self):
        test_type_info = ActorTypeInformation.create(FakeSimpleActor)
        ctx = ActorRuntimeContext(
            test_type_info, self._serializer,
            self._serializer, self._fake_client)
        manager = ActorManager(ctx)
        with self.assertRaises(ValueError):
            await manager.fire_reminder(ActorId('testid'), 'test_reminder', self._test_reminder_req)

    async def test_fire_reminder_success(self):
        test_actor_id = ActorId('testid')
        test_type_info = ActorTypeInformation.create(FakeSimpleReminderActor)
        ctx = ActorRuntimeContext(
            test_type_info, self._serializer,
            self._serializer, self._fake_client)
        manager = ActorManager(ctx)
        await manager.activate_actor(test_actor_id)
        await manager.fire_reminder(test_actor_id, 'test_reminder', self._test_reminder_req)


class ActorManagerTimerTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self._serializer = DefaultJSONSerializer()

        self._fake_client = AsyncMock()
        self._fake_client.invoke_method.return_value = b'"expected_response"'
        self._fake_client.register_timer.return_value = b'"ok"'

    async def test_fire_timer_success(self):
        test_actor_id = ActorId('testid')
        test_type_info = ActorTypeInformation.create(FakeSimpleTimerActor)
        ctx = ActorRuntimeContext(
            test_type_info, self._serializer,
            self._serializer, self._fake_client)
        manager = ActorManager(ctx)

        await manager.activate_actor(test_actor_id)
        actor = manager._active_actors.get(test_actor_id.id, None)

        # Setup timer
        await actor.register_timer(
            'test_timer', actor.timer_callback,
            "timer call", timedelta(seconds=1), timedelta(seconds=1))

        # Fire timer
        await manager.fire_timer(test_actor_id, 'test_timer')

        self.assertTrue(actor.timer_called)
