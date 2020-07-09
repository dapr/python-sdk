# -*- coding: utf-8 -*-

"""
Copyright (c) Microsoft Corporation.
Licensed under the MIT License.
"""

import unittest
from unittest.mock import AsyncMock

from dapr.actor.runtime.context import ActorRuntimeContext
from dapr.actor.runtime.method_dispatcher import ActorMethodDispatcher
from dapr.actor.runtime._type_information import ActorTypeInformation
from dapr.serializers import DefaultJSONSerializer

from tests.actor.fake_actor_classes import FakeSimpleActor


class ActorMethodDispatcherTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self._testActorTypeInfo = ActorTypeInformation.create(FakeSimpleActor)
        self._serializer = DefaultJSONSerializer()
        self._fake_client = AsyncMock()
        self._fake_runtime_ctx = ActorRuntimeContext(
            self._testActorTypeInfo, self._serializer,
            self._serializer, self._fake_client)

    def test_get_arg_names(self):
        dispatcher = ActorMethodDispatcher(self._testActorTypeInfo)
        arg_names = dispatcher.get_arg_names("ActorMethod")
        self.assertEqual(['arg'], arg_names)

    def test_get_arg_types(self):
        dispatcher = ActorMethodDispatcher(self._testActorTypeInfo)
        arg_names = dispatcher.get_arg_types("ActorMethod")
        self.assertEqual([int], arg_names)

    def test_get_return_type(self):
        dispatcher = ActorMethodDispatcher(self._testActorTypeInfo)
        arg_names = dispatcher.get_return_type("ActorMethod")
        self.assertEqual(dict, arg_names)

    async def test_dispatch(self):
        dispatcher = ActorMethodDispatcher(self._testActorTypeInfo)
        actorInstance = FakeSimpleActor(self._fake_runtime_ctx, None)
        result = await dispatcher.dispatch(actorInstance, "ActorMethod", 10)
        self.assertEqual({'name': 'actor_method'}, result)
