# -*- coding: utf-8 -*-

"""
Copyright (c) Microsoft Corporation.
Licensed under the MIT License.
"""

import unittest
from unittest.mock import MagicMock

from dapr.actor.id import ActorId
from dapr.actor.client.proxy import ActorProxy
from dapr.clients import DaprActorClientBase

from .testactorclasses import ManagerTestActorInterface

class FakeActoryProxyFactory:
    def __init__(self, fake_client):
        # TODO: support serializer for state store later
        self._dapr_client = fake_client

    def create(self, actor_interface,
               actor_type, actor_id) -> ActorProxy:
        return ActorProxy(self._dapr_client, actor_interface,
                          actor_type, actor_id)

class ActorProxyTests(unittest.TestCase):
    def setUp(self):
        # Create mock client
        self._mock_client = MagicMock()
        self._mock_client.invoke_method.return_value = b'expected_response'

        self._fake_factory = FakeActoryProxyFactory(self._mock_client)
        self._proxy = ActorProxy.create(
            ManagerTestActorInterface,
            'ManagerTestActor',
            ActorId('fake-id'),
            self._fake_factory)
    
    def test_invoke(self):
        response = self._proxy.invoke('ActionMethod', b'arg0')
        self.assertEqual(b'expected_response', response)
        self._mock_client.invoke_method.assert_called_once_with('ManagerTestActor', 'fake-id', 'ActionMethod', b'arg0')
