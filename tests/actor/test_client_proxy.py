# -*- coding: utf-8 -*-

"""
Copyright (c) Microsoft Corporation.
Licensed under the MIT License.
"""

import unittest
import asyncio

from unittest import mock

from dapr.actor.id import ActorId
from dapr.actor.client.proxy import ActorProxy
from dapr.serializers import DefaultJSONSerializer

from tests.actor.fake_actor_classes import (
    FakeDaprActorClient,
    FakeMultiInterfacesActor,
    FakeActorCls2Interface,
)

def async_mock(*args, **kwargs):
    m = mock.MagicMock(*args, **kwargs)

    async def mock_coro(*args, **kwargs):
        return m(*args, **kwargs)

    mock_coro.mock = m
    return mock_coro

def _run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)

class FakeActoryProxyFactory:
    def __init__(self, fake_client):
        # TODO: support serializer for state store later
        self._dapr_client = fake_client

    def create(self, actor_interface,
               actor_type, actor_id) -> ActorProxy:
        return ActorProxy(self._dapr_client, actor_interface,
                          actor_type, actor_id, DefaultJSONSerializer())


class ActorProxyTests(unittest.TestCase):

    @mock.patch('tests.actor.fake_actor_classes.FakeDaprActorClient.invoke_method', new=async_mock(return_value=b'"expected_response"'))
    def test_invoke(self):
        _fake_client = FakeDaprActorClient

        _fake_factory = FakeActoryProxyFactory(_fake_client)
        _proxy = ActorProxy.create(
            FakeMultiInterfacesActor.__name__,
            ActorId('fake-id'),
            FakeActorCls2Interface,
            _fake_factory)

        response = _run(_proxy.invoke('ActionMethod', b'arg0'))
        self.assertEqual(b'"expected_response"', response)
        _fake_client.invoke_method.mock.assert_called_once_with(
            FakeMultiInterfacesActor.__name__, 'fake-id', 'ActionMethod', b'arg0')

    @mock.patch('tests.actor.fake_actor_classes.FakeDaprActorClient.invoke_method', new=async_mock(return_value=b'"expected_response"'))
    def test_invoke_no_arg(self):
        _fake_client = FakeDaprActorClient

        _fake_factory = FakeActoryProxyFactory(_fake_client)
        _proxy = ActorProxy.create(
            FakeMultiInterfacesActor.__name__,
            ActorId('fake-id'),
            FakeActorCls2Interface,
            _fake_factory)
        
        response = _run(_proxy.invoke('ActionMethodWithoutArg'))
        self.assertEqual(b'"expected_response"', response)
        _fake_client.invoke_method.mock.assert_called_once_with(
            FakeMultiInterfacesActor.__name__, 'fake-id', 'ActionMethodWithoutArg', None)

    @mock.patch('tests.actor.fake_actor_classes.FakeDaprActorClient.invoke_method', new=async_mock(return_value=b'"expected_response"'))
    def test_invoke_with_static_typing(self):
        _fake_client = FakeDaprActorClient

        _fake_factory = FakeActoryProxyFactory(_fake_client)
        _proxy = ActorProxy.create(
            FakeMultiInterfacesActor.__name__,
            ActorId('fake-id'),
            FakeActorCls2Interface,
            _fake_factory)
        
        response = _run((_proxy.ActionMethod(b'arg0')))
        self.assertEqual('expected_response', response)
        _fake_client.invoke_method.mock.assert_called_once_with(
            FakeMultiInterfacesActor.__name__, 'fake-id', 'ActionMethod', b'arg0')

    @mock.patch('tests.actor.fake_actor_classes.FakeDaprActorClient.invoke_method', new=async_mock(return_value=b'"expected_response"'))
    def test_invoke_with_static_typing_no_arg(self):
        _fake_client = FakeDaprActorClient

        _fake_factory = FakeActoryProxyFactory(_fake_client)
        _proxy = ActorProxy.create(
            FakeMultiInterfacesActor.__name__,
            ActorId('fake-id'),
            FakeActorCls2Interface,
            _fake_factory)
        
        response = _run(_proxy.ActionMethodWithoutArg())
        self.assertEqual('expected_response', response)
        _fake_client.invoke_method.mock.assert_called_once_with(
            FakeMultiInterfacesActor.__name__, 'fake-id', 'ActionMethodWithoutArg', None)

    def test_raise_exception_non_existing_method(self):
        with self.assertRaises(AttributeError):
            _run(self._proxy.non_existing())
