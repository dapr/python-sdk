# -*- coding: utf-8 -*-

"""
Copyright (c) Microsoft Corporation.
Licensed under the MIT License.
"""

import io
import unittest

from dapr.actor.id import ActorId
from dapr.actor.runtime.typeinformation import ActorTypeInformation
from dapr.actor.runtime.manager import ActorManager
from dapr.actor.runtime.runtime_context import ActorRuntimeContext
from dapr.serializers import DefaultJSONSerializer

from .testactorclasses import ManagerTestActor

class ActorManagerTests(unittest.TestCase):
    def setUp(self):
        self._test_type_info = ActorTypeInformation.create(ManagerTestActor)
        self._serializer = DefaultJSONSerializer()
        self._runtime_ctx = ActorRuntimeContext(self._test_type_info, self._serializer)
        self._manager = ActorManager(self._runtime_ctx)

    def test_activate_actor(self):
        """Activate ActorId(1)"""
        test_actor_id = ActorId('1')
        self._manager.activate_actor(test_actor_id)

        # assert
        self.assertEqual(test_actor_id, self._manager._active_actors[test_actor_id.id].id)
        self.assertTrue(self._manager._active_actors[test_actor_id.id].activated)
        self.assertFalse(self._manager._active_actors[test_actor_id.id].deactivated)

    def test_deactivate_actor(self):
        """Activate ActorId('2') and deactivate it"""
        test_actor_id = ActorId('2')
        self._manager.activate_actor(test_actor_id)

        # assert
        self.assertEqual(test_actor_id, self._manager._active_actors[test_actor_id.id].id)
        self.assertTrue(self._manager._active_actors[test_actor_id.id].activated)
        self.assertFalse(self._manager._active_actors[test_actor_id.id].deactivated)

        self._manager.deactivate_actor(test_actor_id)
        self.assertIsNone(self._manager._active_actors.get(test_actor_id.id))

    def test_dispatch_success(self):
        """dispatch ActionMethod"""
        test_actor_id = ActorId('dispatch')
        self._manager.activate_actor(test_actor_id)

        request_body = {
            "message": "hello dapr",
        }

        test_request_stream = io.BytesIO(self._serializer.serialize(request_body))
        response = self._manager.dispatch(test_actor_id, "ActionMethod", test_request_stream)
        self.assertEqual(b'"hello dapr"', response)