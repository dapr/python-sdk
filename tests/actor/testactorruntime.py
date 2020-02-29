# -*- coding: utf-8 -*-

"""
Copyright (c) Microsoft Corporation.
Licensed under the MIT License.
"""

import asyncio
import io
import unittest

from datetime import timedelta

from dapr.actor.runtime.runtime import ActorRuntime
from dapr.actor.runtime.config import ActorRuntimeConfig
from dapr.serializers import DefaultJSONSerializer

from .testactorclasses import *

class ActorRuntimeTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        ActorRuntime._actor_managers = {}
        self._serializer = DefaultJSONSerializer()
        ActorRuntime.register_actor(TestActor)
        ActorRuntime.register_actor(TestActorImpl)

    def test_get_registered_actor_types(self):
        actor_types = ActorRuntime.get_registered_actor_types()
        self.assertTrue(actor_types.index('TestActor') >= 0)
        self.assertTrue(actor_types.index('TestActorImpl') >= 0)

    def test_actor_config(self):
        config = ActorRuntime.get_actor_config()

        self.assertTrue(config.drainRebalancedActors)
        self.assertEqual(timedelta(hours=1), config.actorIdleTimeout)
        self.assertEqual(timedelta(seconds=30), config.actorScanInterval)
        self.assertEqual(timedelta(minutes=1), config.drainOngoingCallTimeout)
        self.assertEqual(2, len(config.entities))

        # apply new config
        new_config = ActorRuntimeConfig(
            False, timedelta(hours=3),
            timedelta(seconds=10), timedelta(minutes=1))

        ActorRuntime.set_actor_config(new_config)
        config = ActorRuntime.get_actor_config()

        self.assertFalse(config.drainRebalancedActors)
        self.assertEqual(timedelta(hours=3), config.actorIdleTimeout)
        self.assertEqual(timedelta(seconds=10), config.actorScanInterval)
        self.assertEqual(timedelta(minutes=1), config.drainOngoingCallTimeout)
        self.assertEqual(2, len(config.entities))

    def test_entities_update(self):
        config = ActorRuntime.get_actor_config()
        with self.assertRaises(ValueError):
            config.entities.index('ManagerTestActor')

        ActorRuntime.register_actor(ManagerTestActor)
        config = ActorRuntime.get_actor_config()
        self.assertTrue(config.entities.index('ManagerTestActor') >= 0)

    async def test_dispatch(self):
        ActorRuntime.register_actor(ManagerTestActor)
        await ActorRuntime.activate('ManagerTestActor', 'test-id')
        
        request_body = {
            "message": "hello dapr",
        }

        test_request_stream = io.BytesIO(self._serializer.serialize(request_body))
        response = await ActorRuntime.dispatch('ManagerTestActor', 'test-id', "ActionMethod", test_request_stream)

        self.assertEqual(b'"hello dapr"', response)

        await ActorRuntime.deactivate('ManagerTestActor', 'test-id')

        # Ensure test-id is deactivated
        with self.assertRaises(ValueError):
            await ActorRuntime.deactivate('ManagerTestActor', 'test-id')
