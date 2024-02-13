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

from unittest import mock
from datetime import timedelta

from dapr.actor.id import ActorId
from dapr.actor.runtime.config import ActorRuntimeConfig
from dapr.actor.runtime.context import ActorRuntimeContext
from dapr.actor.runtime.runtime import ActorRuntime
from dapr.actor.runtime._type_information import ActorTypeInformation
from dapr.conf import settings
from dapr.serializers import DefaultJSONSerializer

from tests.actor.fake_actor_classes import (
    FakeSimpleActor,
    FakeSimpleReminderActor,
    FakeSimpleTimerActor,
    FakeMultiInterfacesActor,
)

from tests.actor.fake_client import FakeDaprActorClient
from tests.actor.utils import _async_mock, _run
from tests.clients.fake_http_server import FakeHttpServer


class ActorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = FakeHttpServer(3500)
        cls.server.start()
        settings.DAPR_HTTP_PORT = 3500

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown_server()

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
            timedelta(hours=3), timedelta(seconds=10), timedelta(minutes=1), False
        )

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
        self.assertFalse(FakeSimpleActor.__name__ in config._entities)

        _run(ActorRuntime.register_actor(FakeSimpleActor))
        config = ActorRuntime.get_actor_config()
        self.assertTrue(FakeSimpleActor.__name__ in config._entities)

    def test_dispatch(self):
        _run(ActorRuntime.register_actor(FakeMultiInterfacesActor))

        request_body = {
            'message': 'hello dapr',
        }

        test_request_body = self._serializer.serialize(request_body)
        response = _run(
            ActorRuntime.dispatch(
                FakeMultiInterfacesActor.__name__, 'test-id', 'ActionMethod', test_request_body
            )
        )

        self.assertEqual(b'"hello dapr"', response)

        _run(ActorRuntime.deactivate(FakeMultiInterfacesActor.__name__, 'test-id'))

        # Ensure test-id is deactivated
        with self.assertRaises(ValueError):
            _run(ActorRuntime.deactivate(FakeMultiInterfacesActor.__name__, 'test-id'))

    @mock.patch(
        'tests.actor.fake_client.FakeDaprActorClient.register_reminder',
        new=_async_mock(return_value=b'"ok"'),
    )
    @mock.patch(
        'tests.actor.fake_client.FakeDaprActorClient.unregister_reminder',
        new=_async_mock(return_value=b'"ok"'),
    )
    def test_register_reminder(self):
        test_actor_id = ActorId('test_id')
        test_type_info = ActorTypeInformation.create(FakeSimpleReminderActor)
        test_client = FakeDaprActorClient
        ctx = ActorRuntimeContext(test_type_info, self._serializer, self._serializer, test_client)
        test_actor = FakeSimpleReminderActor(ctx, test_actor_id)

        # register reminder
        _run(
            test_actor.register_reminder(
                'test_reminder', b'reminder_message', timedelta(seconds=1), timedelta(seconds=1)
            )
        )
        test_client.register_reminder.mock.assert_called_once()
        test_client.register_reminder.mock.assert_called_with(
            'FakeSimpleReminderActor',
            'test_id',
            'test_reminder',
            b'{"reminderName":"test_reminder","dueTime":"0h0m1s0ms0\\u03bcs","period":"0h0m1s0ms0\\u03bcs","data":"cmVtaW5kZXJfbWVzc2FnZQ=="}',
        )  # noqa E501

        # unregister reminder
        _run(test_actor.unregister_reminder('test_reminder'))
        test_client.unregister_reminder.mock.assert_called_once()
        test_client.unregister_reminder.mock.assert_called_with(
            'FakeSimpleReminderActor', 'test_id', 'test_reminder'
        )

    @mock.patch(
        'tests.actor.fake_client.FakeDaprActorClient.register_timer',
        new=_async_mock(return_value=b'"ok"'),
    )
    @mock.patch(
        'tests.actor.fake_client.FakeDaprActorClient.unregister_timer',
        new=_async_mock(return_value=b'"ok"'),
    )
    def test_register_timer(self):
        test_actor_id = ActorId('test_id')
        test_type_info = ActorTypeInformation.create(FakeSimpleTimerActor)
        test_client = FakeDaprActorClient
        ctx = ActorRuntimeContext(test_type_info, self._serializer, self._serializer, test_client)
        test_actor = FakeSimpleTimerActor(ctx, test_actor_id)

        # register timer
        _run(
            test_actor.register_timer(
                'test_timer',
                test_actor.timer_callback,
                'mydata',
                timedelta(seconds=1),
                timedelta(seconds=2),
            )
        )
        test_client.register_timer.mock.assert_called_once()
        test_client.register_timer.mock.assert_called_with(
            'FakeSimpleTimerActor',
            'test_id',
            'test_timer',
            b'{"callback":"timer_callback","data":"mydata","dueTime":"0h0m1s0ms0\\u03bcs","period":"0h0m2s0ms0\\u03bcs"}',
        )  # noqa E501

        # unregister timer
        _run(test_actor.unregister_timer('test_timer'))
        test_client.unregister_timer.mock.assert_called_once()
        test_client.unregister_timer.mock.assert_called_with(
            'FakeSimpleTimerActor', 'test_id', 'test_timer'
        )

        # register timer without timer name
        _run(
            test_actor.register_timer(
                None,
                test_actor.timer_callback,
                'timer call',
                timedelta(seconds=1),
                timedelta(seconds=1),
            )
        )
