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


from dapr.actor.id import ActorId
from dapr.actor.client.proxy import ActorProxy
from dapr.serializers import DefaultJSONSerializer
from tests.actor.fake_actor_classes import (
    FakeMultiInterfacesActor,
    FakeActorCls2Interface,
)


from tests.actor.fake_client import FakeDaprActorClient

from tests.actor.utils import _async_mock, _run


class FakeActoryProxyFactory:
    def __init__(self, fake_client):
        # TODO: support serializer for state store later
        self._dapr_client = fake_client

    def create(self, actor_interface, actor_type, actor_id) -> ActorProxy:
        return ActorProxy(
            self._dapr_client, actor_interface, actor_type, actor_id, DefaultJSONSerializer()
        )


class ActorProxyTests(unittest.TestCase):
    def setUp(self):
        # Create mock client
        self._fake_client = FakeDaprActorClient
        self._fake_factory = FakeActoryProxyFactory(self._fake_client)
        self._proxy = ActorProxy.create(
            FakeMultiInterfacesActor.__name__,
            ActorId('fake-id'),
            FakeActorCls2Interface,
            self._fake_factory,
        )

    @mock.patch(
        'tests.actor.fake_client.FakeDaprActorClient.invoke_method',
        new=_async_mock(return_value=b'"expected_response"'),
    )
    def test_invoke(self):
        response = _run(self._proxy.invoke_method('ActionMethod', b'arg0'))
        self.assertEqual(b'"expected_response"', response)
        self._fake_client.invoke_method.mock.assert_called_once_with(
            FakeMultiInterfacesActor.__name__, 'fake-id', 'ActionMethod', b'arg0'
        )

    @mock.patch(
        'tests.actor.fake_client.FakeDaprActorClient.invoke_method',
        new=_async_mock(return_value=b'"expected_response"'),
    )
    def test_invoke_no_arg(self):
        response = _run(self._proxy.invoke_method('ActionMethodWithoutArg'))
        self.assertEqual(b'"expected_response"', response)
        self._fake_client.invoke_method.mock.assert_called_once_with(
            FakeMultiInterfacesActor.__name__, 'fake-id', 'ActionMethodWithoutArg', None
        )

    @mock.patch(
        'tests.actor.fake_client.FakeDaprActorClient.invoke_method',
        new=_async_mock(return_value=b'"expected_response"'),
    )
    def test_invoke_with_static_typing(self):
        response = _run(self._proxy.ActionMethod(b'arg0'))
        self.assertEqual('expected_response', response)
        self._fake_client.invoke_method.mock.assert_called_once_with(
            FakeMultiInterfacesActor.__name__, 'fake-id', 'ActionMethod', b'arg0'
        )

    @mock.patch(
        'tests.actor.fake_client.FakeDaprActorClient.invoke_method',
        new=_async_mock(return_value=b'"expected_response"'),
    )
    def test_invoke_with_static_typing_no_arg(self):
        response = _run(self._proxy.ActionMethodWithoutArg())
        self.assertEqual('expected_response', response)
        self._fake_client.invoke_method.mock.assert_called_once_with(
            FakeMultiInterfacesActor.__name__, 'fake-id', 'ActionMethodWithoutArg', None
        )

    def test_raise_exception_non_existing_method(self):
        with self.assertRaises(AttributeError):
            _run(self._proxy.non_existing())
