# -*- coding: utf-8 -*-

"""
Copyright (c) Microsoft Corporation.
Licensed under the MIT License.
"""

import unittest
from unittest.mock import AsyncMock

from dapr.actor.id import ActorId
from dapr.actor.client.proxy import ActorProxy
from dapr.clients import DaprActorClientBase
from dapr.serializers import DefaultJSONSerializer

from .testactorclasses import ManagerTestActorInterface

class FakeActoryProxyFactory:
    def __init__(self, fake_client):
        # TODO: support serializer for state store later
        self._dapr_client = fake_client

    def create(self, actor_interface,
               actor_type, actor_id) -> ActorProxy:
        return ActorProxy(self._dapr_client, actor_interface,
                          actor_type, actor_id, DefaultJSONSerializer())

class ActorProxyTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        # Create mock client
        self._mock_client = AsyncMock()
        self._mock_client.invoke_method.return_value = b'"expected_response"'

        self._fake_factory = FakeActoryProxyFactory(self._mock_client)
        self._proxy = ActorProxy.create(
            ManagerTestActorInterface,
            'ManagerTestActor',
            ActorId('fake-id'),
            self._fake_factory)
    
    async def test_invoke(self):
        response = await self._proxy.invoke('ActionMethod', b'arg0')
        self.assertEqual(b'"expected_response"', response)
        self._mock_client.invoke_method.assert_called_once_with('ManagerTestActor', 'fake-id', 'ActionMethod', b'arg0')

    async def test_invoke_with_static_typing(self):
        response = await self._proxy.ActionMethod(b'arg0')
        self.assertEqual('expected_response', response)
        self._mock_client.invoke_method.assert_called_once_with('ManagerTestActor', 'fake-id', 'ActionMethod', b'arg0')
