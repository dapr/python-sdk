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

from dapr.actor.runtime.context import ActorRuntimeContext
from dapr.actor.runtime.method_dispatcher import ActorMethodDispatcher
from dapr.actor.runtime._type_information import ActorTypeInformation
from dapr.serializers import DefaultJSONSerializer

from tests.actor.fake_actor_classes import FakeSimpleActor
from tests.actor.fake_client import FakeDaprActorClient
from tests.actor.utils import _run


class ActorMethodDispatcherTests(unittest.TestCase):
    def setUp(self):
        self._testActorTypeInfo = ActorTypeInformation.create(FakeSimpleActor)
        self._serializer = DefaultJSONSerializer()
        self._fake_client = FakeDaprActorClient
        self._fake_runtime_ctx = ActorRuntimeContext(
            self._testActorTypeInfo, self._serializer, self._serializer, self._fake_client
        )

    def test_get_arg_names(self):
        dispatcher = ActorMethodDispatcher(self._testActorTypeInfo)
        arg_names = dispatcher.get_arg_names('ActorMethod')
        self.assertEqual(['arg'], arg_names)

    def test_get_arg_types(self):
        dispatcher = ActorMethodDispatcher(self._testActorTypeInfo)
        arg_names = dispatcher.get_arg_types('ActorMethod')
        self.assertEqual([int], arg_names)

    def test_get_return_type(self):
        dispatcher = ActorMethodDispatcher(self._testActorTypeInfo)
        arg_names = dispatcher.get_return_type('ActorMethod')
        self.assertEqual(dict, arg_names)

    def test_dispatch(self):
        dispatcher = ActorMethodDispatcher(self._testActorTypeInfo)
        actorInstance = FakeSimpleActor(self._fake_runtime_ctx, None)
        result = _run(dispatcher.dispatch(actorInstance, 'ActorMethod', 10))
        self.assertEqual({'name': 'actor_method'}, result)
