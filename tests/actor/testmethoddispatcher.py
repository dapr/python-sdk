# -*- coding: utf-8 -*-

"""
Copyright (c) Microsoft Corporation.
Licensed under the MIT License.
"""

import unittest

from dapr.actor.runtime.typeinformation import ActorTypeInformation
from dapr.actor.runtime.method_dispatcher import ActorMethodDispatcher

from .testactorclasses import TestActor

class ActorMethodDispatcherTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self._testActorTypeInfo = ActorTypeInformation.create(TestActor)

    def test_get_arg_names(self):
        dispatcher = ActorMethodDispatcher(self._testActorTypeInfo)
        arg_names = dispatcher.get_arg_names("ActorMethod")
        self.assertEqual([ 'arg' ], arg_names)

    def test_get_arg_types(self):
        dispatcher = ActorMethodDispatcher(self._testActorTypeInfo)
        arg_names = dispatcher.get_arg_types("ActorMethod")
        self.assertEqual([ int ], arg_names)

    def test_get_return_type(self):
        dispatcher = ActorMethodDispatcher(self._testActorTypeInfo)
        arg_names = dispatcher.get_return_type("ActorMethod")
        self.assertEqual(dict, arg_names)

    async def test_dispatch(self):
        dispatcher = ActorMethodDispatcher(self._testActorTypeInfo)
        actorInstance = TestActor(None, None)
        result = await dispatcher.dispatch(actorInstance, "ActorMethod", 10)
        self.assertEqual({'name': 'actor_method'}, result)
