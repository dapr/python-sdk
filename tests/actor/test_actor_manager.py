# -*- coding: utf-8 -*-

"""
Copyright 2021 The Dapr Authors
Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at
    http://www.apache.org/licenses/LICENSE-2.0
Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
"""

import unittest
from datetime import timedelta
from unittest import mock

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

from tests.actor.fake_client import FakeDaprActorClient

from tests.actor.utils import (
    _async_mock,
    _run,
)


class ActorManagerTests(unittest.TestCase):
    def setUp(self):
        self._test_type_info = ActorTypeInformation.create(FakeMultiInterfacesActor)
        self._serializer = DefaultJSONSerializer()

        self._fake_client = FakeDaprActorClient
        self._runtime_ctx = ActorRuntimeContext(
            self._test_type_info, self._serializer, self._serializer, self._fake_client
        )
        self._manager = ActorManager(self._runtime_ctx)

    def test_activate_actor(self):
        """Activate ActorId(1)"""
        test_actor_id = ActorId('1')
        _run(self._manager.activate_actor(test_actor_id))

        # assert
        self.assertEqual(test_actor_id, self._manager._active_actors[test_actor_id.id].id)
        self.assertTrue(self._manager._active_actors[test_actor_id.id].activated)
        self.assertFalse(self._manager._active_actors[test_actor_id.id].deactivated)

    def test_deactivate_actor(self):
        """Activate ActorId('2') and deactivate it"""
        test_actor_id = ActorId('2')
        _run(self._manager.activate_actor(test_actor_id))

        # assert
        self.assertEqual(test_actor_id, self._manager._active_actors[test_actor_id.id].id)
        self.assertTrue(self._manager._active_actors[test_actor_id.id].activated)
        self.assertFalse(self._manager._active_actors[test_actor_id.id].deactivated)

        _run(self._manager.deactivate_actor(test_actor_id))
        self.assertIsNone(self._manager._active_actors.get(test_actor_id.id))

    def test_dispatch_success(self):
        """dispatch ActionMethod"""
        test_actor_id = ActorId('dispatch')
        _run(self._manager.activate_actor(test_actor_id))

        request_body = {
            'message': 'hello dapr',
        }

        test_request_body = self._serializer.serialize(request_body)
        response = _run(self._manager.dispatch(test_actor_id, 'ActionMethod', test_request_body))
        self.assertEqual(b'"hello dapr"', response)


class ActorManagerReminderTests(unittest.TestCase):
    def setUp(self):
        self._serializer = DefaultJSONSerializer()
        self._fake_client = FakeDaprActorClient

        self._test_reminder_req = self._serializer.serialize(
            {
                'name': 'test_reminder',
                'dueTime': timedelta(seconds=1),
                'period': timedelta(seconds=1),
                'ttl': timedelta(seconds=1),
                'data': 'cmVtaW5kZXJfc3RhdGU=',
            }
        )

    def test_fire_reminder_for_non_reminderable(self):
        test_type_info = ActorTypeInformation.create(FakeSimpleActor)
        ctx = ActorRuntimeContext(
            test_type_info, self._serializer, self._serializer, self._fake_client
        )
        manager = ActorManager(ctx)
        with self.assertRaises(ValueError):
            _run(manager.fire_reminder(ActorId('testid'), 'test_reminder', self._test_reminder_req))

    def test_fire_reminder_success(self):
        test_actor_id = ActorId('testid')
        test_type_info = ActorTypeInformation.create(FakeSimpleReminderActor)
        ctx = ActorRuntimeContext(
            test_type_info, self._serializer, self._serializer, self._fake_client
        )
        manager = ActorManager(ctx)
        _run(manager.activate_actor(test_actor_id))
        _run(manager.fire_reminder(test_actor_id, 'test_reminder', self._test_reminder_req))


class ActorManagerTimerTests(unittest.TestCase):
    def setUp(self):
        self._serializer = DefaultJSONSerializer()

        self._fake_client = FakeDaprActorClient

    @mock.patch(
        'tests.actor.fake_client.FakeDaprActorClient.invoke_method',
        new=_async_mock(return_value=b'"expected_response"'),
    )
    @mock.patch('tests.actor.fake_client.FakeDaprActorClient.register_timer', new=_async_mock())
    def test_fire_timer_success(self):
        test_actor_id = ActorId('testid')
        test_type_info = ActorTypeInformation.create(FakeSimpleTimerActor)
        ctx = ActorRuntimeContext(
            test_type_info, self._serializer, self._serializer, self._fake_client
        )
        manager = ActorManager(ctx)

        _run(manager.activate_actor(test_actor_id))
        actor = manager._active_actors.get(test_actor_id.id, None)

        # Setup timer
        _run(
            actor.register_timer(
                'test_timer',
                actor.timer_callback,
                'timer call',
                timedelta(seconds=1),
                timedelta(seconds=1),
                timedelta(seconds=1),
            )
        )

        # Fire timer
        _run(
            manager.fire_timer(
                test_actor_id,
                'test_timer',
                '{ "callback": "timer_callback", "data": "timer call" }'.encode('UTF8'),
            )
        )

        self.assertTrue(actor.timer_called)
