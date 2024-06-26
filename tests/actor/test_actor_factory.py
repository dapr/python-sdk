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

from dapr.actor import Actor
from dapr.actor.id import ActorId
from dapr.actor.runtime._type_information import ActorTypeInformation
from dapr.actor.runtime.manager import ActorManager
from dapr.actor.runtime.context import ActorRuntimeContext
from dapr.serializers import DefaultJSONSerializer

from tests.actor.fake_actor_classes import (
    FakeSimpleActorInterface,
)

from tests.actor.fake_client import FakeDaprActorClient

from tests.actor.utils import _run


class FakeDependency:
    def __init__(self, value: str):
        self.value = value

    def get_value(self) -> str:
        return self.value


class FakeSimpleActorWithDependency(Actor, FakeSimpleActorInterface):
    def __init__(self, ctx, actor_id, dependency: FakeDependency):
        super(FakeSimpleActorWithDependency, self).__init__(ctx, actor_id)
        self.dependency = dependency

    async def actor_method(self, arg: int) -> dict:
        return {'name': f'{arg}-{self.dependency.get_value()}'}

    async def _on_activate(self):
        self.activated = True
        self.deactivated = False

    async def _on_deactivate(self):
        self.activated = False
        self.deactivated = True


def an_actor_factory(ctx: 'ActorRuntimeContext', actor_id: ActorId) -> 'Actor':
    dependency = FakeDependency('some-value')
    return ctx.actor_type_info.implementation_type(ctx, actor_id, dependency)


class ActorFactoryTests(unittest.TestCase):
    def setUp(self):
        self._test_type_info = ActorTypeInformation.create(FakeSimpleActorWithDependency)
        self._serializer = DefaultJSONSerializer()

        self._fake_client = FakeDaprActorClient
        self._runtime_ctx = ActorRuntimeContext(
            self._test_type_info,
            self._serializer,
            self._serializer,
            self._fake_client,
            an_actor_factory,
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

    def test_dispatch_success(self):
        """dispatch ActionMethod"""
        test_actor_id = ActorId('dispatch')
        _run(self._manager.activate_actor(test_actor_id))

        test_request_body = b'5'
        response = _run(self._manager.dispatch(test_actor_id, 'ActorMethod', test_request_body))
        self.assertEqual(b'{"name":"5-some-value"}', response)
