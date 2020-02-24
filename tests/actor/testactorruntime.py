# -*- coding: utf-8 -*-

"""
Copyright (c) Microsoft Corporation.
Licensed under the MIT License.
"""

import io
import unittest

from datetime import timedelta

from dapr.actor.runtime.runtime import ActorRuntime
from dapr.actor.runtime.runtime_config import ActorRuntimeConfig
from dapr.serializers import DefaultJSONSerializer

from .testactorclasses import *

class ActorRuntimeTests(unittest.TestCase):
    def setUp(self):
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

    def test_dispatch(self):
        ActorRuntime.register_actor(ManagerTestActor)
        ActorRuntime.activate('ManagerTestActor', 'test-id')
        
        request_body = {
            "message": "hello dapr",
        }

        test_request_stream = io.BytesIO(self._serializer.serialize(request_body))
        response = ActorRuntime.dispatch('ManagerTestActor', 'test-id', "ActionMethod", test_request_stream)

        self.assertEqual(b'"hello dapr"', response)

        ActorRuntime.deactivate('ManagerTestActor', 'test-id')

        # Ensure test-id is deactivated
        with self.assertRaises(ValueError):
            ActorRuntime.deactivate('ManagerTestActor', 'test-id')