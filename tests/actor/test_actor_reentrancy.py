# -*- coding: utf-8 -*-

"""
Copyright (c) Microsoft Corporation and Dapr Contributors.
Licensed under the MIT License.
"""

from ext.flask_dapr import flask_dapr
import unittest
import asyncio

from unittest import mock

from dapr.actor.runtime.runtime import ActorRuntime
from dapr.actor.runtime.config import ActorRuntimeConfig, ActorReentrancyConfig
from dapr.serializers import DefaultJSONSerializer

from tests.actor.fake_actor_classes import (
    FakeReentrantActor,
    FakeMultiInterfacesActor,
    FakeSlowReentrantActor,
)

from tests.actor.utils import _run


class ActorRuntimeTests(unittest.TestCase):
    def setUp(self):
        ActorRuntime._actor_managers = {}
        ActorRuntime.set_actor_config(
            ActorRuntimeConfig(reentrancy=ActorReentrancyConfig(enabled=True)))
        self._serializer = DefaultJSONSerializer()
        _run(ActorRuntime.register_actor(FakeReentrantActor))
        _run(ActorRuntime.register_actor(FakeSlowReentrantActor))
        _run(ActorRuntime.register_actor(FakeMultiInterfacesActor))

    def test_reentrant_dispatch(self):
        _run(ActorRuntime.register_actor(FakeMultiInterfacesActor))

        request_body = {
            "message": "hello dapr",
        }

        reentrancy_id = "0faa4c8b-f53a-4dff-9a9d-c50205035085"

        test_request_body = self._serializer.serialize(request_body)
        response = _run(ActorRuntime.dispatch(
            FakeMultiInterfacesActor.__name__, 'test-id',
            "ReentrantMethod", test_request_body, reentrancy_id=reentrancy_id))

        self.assertEqual(b'"hello dapr"', response)

        _run(ActorRuntime.deactivate(FakeMultiInterfacesActor.__name__, 'test-id'))

        # Ensure test-id is deactivated
        with self.assertRaises(ValueError):
            _run(ActorRuntime.deactivate(FakeMultiInterfacesActor.__name__, 'test-id'))

    def test_interleaved_reentrant_actor_dispatch(self):
        _run(ActorRuntime.register_actor(FakeReentrantActor))
        _run(ActorRuntime.register_actor(FakeSlowReentrantActor))

        request_body = self._serializer.serialize({
            "message": "Normal",
        })

        normal_reentrancy_id = "f6319f23-dc0a-4880-90d9-87b23c19c20a"
        slow_reentrancy_id = "b1653a2f-fe54-4514-8197-98b52d156454"

        async def dispatchReentrantCall(actorName: str, method: str, reentrancy_id: str):
            return await ActorRuntime.dispatch(
                actorName, 'test-id', method, request_body, reentrancy_id=reentrancy_id)

        async def run_parallel_actors():
            slow = dispatchReentrantCall(
                FakeSlowReentrantActor.__name__, "ReentrantMethod", slow_reentrancy_id)
            normal = dispatchReentrantCall(
                FakeReentrantActor.__name__, "ReentrantMethod", normal_reentrancy_id)

            res = await asyncio.gather(slow, normal)
            self.slow_res = res[0]
            self.normal_res = res[1]

        _run(run_parallel_actors())

        self.assertEqual(self.normal_res, bytes('"' + normal_reentrancy_id + '"', 'utf-8'))
        self.assertEqual(self.slow_res, bytes('"' + slow_reentrancy_id + '"', 'utf-8'))

        _run(ActorRuntime.deactivate(FakeSlowReentrantActor.__name__, 'test-id'))
        _run(ActorRuntime.deactivate(FakeReentrantActor.__name__, 'test-id'))

        # Ensure test-id is deactivated
        with self.assertRaises(ValueError):
            _run(ActorRuntime.deactivate(FakeSlowReentrantActor.__name__, 'test-id'))
            _run(ActorRuntime.deactivate(FakeReentrantActor.__name__, 'test-id'))

    def test_reentrancy_header_passthrough(self):
        _run(ActorRuntime.register_actor(FakeReentrantActor))
        _run(ActorRuntime.register_actor(FakeSlowReentrantActor))

        request_body = self._serializer.serialize({
            "message": "Normal",
        })

        async def expected_return_value():
            return ["expected", "None"]

        reentrancy_id = "f6319f23-dc0a-4880-90d9-87b23c19c20a"
        actor = FakeSlowReentrantActor.__name__
        method = 'ReentrantMethod'

        with mock.patch('dapr.clients.http.client.DaprHttpClient.send_bytes') as mocked:

            mocked.return_value = expected_return_value()
            _run(ActorRuntime.dispatch(
                 FakeReentrantActor.__name__, 'test-id', 'ReentrantMethodWithPassthrough',
                 request_body, reentrancy_id=reentrancy_id))

            mocked.assert_called_with(
                method="POST",
                url=f'http://127.0.0.1:3500/v1.0/actors/{actor}/test-id/method/{method}',
                data=None,
                headers={'Dapr-Reentrancy-Id': reentrancy_id})

        _run(ActorRuntime.deactivate(FakeReentrantActor.__name__, 'test-id'))

        # Ensure test-id is deactivated
        with self.assertRaises(ValueError):
            _run(ActorRuntime.deactivate(FakeReentrantActor.__name__, 'test-id'))

    def test_header_passthrough_reentrancy_disabled(self):
        config = ActorRuntimeConfig(reentrancy=None)
        ActorRuntime.set_actor_config(config)
        _run(ActorRuntime.register_actor(FakeReentrantActor))
        _run(ActorRuntime.register_actor(FakeSlowReentrantActor))

        request_body = self._serializer.serialize({
            "message": "Normal",
        })

        async def expected_return_value():
            return ["expected", "None"]

        reentrancy_id = "f6319f23-dc0a-4880-90d9-87b23c19c20a"
        actor = FakeSlowReentrantActor.__name__
        method = 'ReentrantMethod'

        with mock.patch('dapr.clients.http.client.DaprHttpClient.send_bytes') as mocked:

            mocked.return_value = expected_return_value()
            _run(ActorRuntime.dispatch(
                FakeReentrantActor.__name__, 'test-id', 'ReentrantMethodWithPassthrough',
                request_body, reentrancy_id=reentrancy_id))

            mocked.assert_called_with(
                method="POST",
                url=f'http://127.0.0.1:3500/v1.0/actors/{actor}/test-id/method/{method}',
                data=None,
                headers={})

        _run(ActorRuntime.deactivate(FakeReentrantActor.__name__, 'test-id'))

        # Ensure test-id is deactivated
        with self.assertRaises(ValueError):
            _run(ActorRuntime.deactivate(FakeReentrantActor.__name__, 'test-id'))

    def test_parse_incoming_reentrancy_header(self):
        _run(ActorRuntime.register_actor(FakeReentrantActor))
        from ext.flask_dapr.flask_dapr import DaprActor
        from flask import Flask

        app = Flask(f'{FakeReentrantActor.__name__}Service')
        DaprActor(app)

        reentrancy_id = "b1653a2f-fe54-4514-8197-98b52d156454"
        actor_type_name = FakeReentrantActor.__name__
        actor_id = 'test-id'
        method_name = 'ReentrantMethod'

        request_body = self._serializer.serialize({
            "message": "Normal",
        })

        relativeUrl = f'/actors/{actor_type_name}/{actor_id}/method/{method_name}'

        with mock.patch('dapr.actor.runtime.runtime.ActorRuntime.dispatch') as mocked:
            client = app.test_client()
            client.put(
                relativeUrl,
                headers={
                    flask_dapr.actor.DAPR_REENTRANCY_ID_HEADER: reentrancy_id},
                method="PUT", data=request_body)
            mocked.return_value = None
            mocked.assert_called_with(
                actor_type_name, actor_id, method_name, request_body, reentrancy_id)
