# -*- coding: utf-8 -*-

"""
Copyright (c) Microsoft Corporation.
Licensed under the MIT License.
"""

import unittest

from datetime import timedelta

from dapr.actor.runtime.runtime import ActorRuntime
from dapr.actor.runtime.config import ActorRuntimeConfig
from dapr.serializers import DefaultJSONSerializer

from tests.actor.fake_actor_classes import (
    FakeSimpleActor,
    FakeMultiInterfacesActor,
)


class ActorRuntimeTests(unittest.IsolatedAsyncioTestCase):
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
            False, timedelta(hours=3),
            timedelta(seconds=10), timedelta(minutes=1))

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
