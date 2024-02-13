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

from dapr.actor.runtime.runtime import ActorRuntime
from dapr.actor.runtime.config import ActorRuntimeConfig
from dapr.conf import settings
from dapr.serializers import DefaultJSONSerializer

from tests.actor.fake_actor_classes import (
    FakeSimpleActor,
    FakeMultiInterfacesActor,
    FakeSimpleTimerActor,
)

from tests.actor.utils import _run
from tests.clients.fake_http_server import FakeHttpServer


class ActorRuntimeTests(unittest.TestCase):
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
        _run(ActorRuntime.register_actor(FakeSimpleTimerActor))

    def test_get_registered_actor_types(self):
        actor_types = ActorRuntime.get_registered_actor_types()
        self.assertTrue(actor_types.index('FakeSimpleActor') >= 0)
        self.assertTrue(actor_types.index(FakeMultiInterfacesActor.__name__) >= 0)
        self.assertTrue(actor_types.index(FakeSimpleTimerActor.__name__) >= 0)

    def test_actor_config(self):
        config = ActorRuntime.get_actor_config()

        self.assertTrue(config._drain_rebalanced_actors)
        self.assertEqual(timedelta(hours=1), config._actor_idle_timeout)
        self.assertEqual(timedelta(seconds=30), config._actor_scan_interval)
        self.assertEqual(timedelta(minutes=1), config._drain_ongoing_call_timeout)
        self.assertEqual(3, len(config._entities))

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
        self.assertEqual(3, len(config._entities))

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

    def test_fire_timer_success(self):
        # Fire timer
        _run(
            ActorRuntime.fire_timer(
                FakeSimpleTimerActor.__name__,
                'test-id',
                'test_timer',
                '{ "callback": "timer_callback", "data": "timer call" }'.encode('UTF8'),
            )
        )

        manager = ActorRuntime._actor_managers[FakeSimpleTimerActor.__name__]
        actor = manager._active_actors['test-id']
        self.assertTrue(actor.timer_called)

    def test_fire_timer_unregistered(self):
        with self.assertRaises(ValueError):
            _run(
                ActorRuntime.fire_timer(
                    'UnknownType',
                    'test-id',
                    'test_timer',
                    '{ "callback": "timer_callback", "data": "timer call" }'.encode('UTF8'),
                )
            )
