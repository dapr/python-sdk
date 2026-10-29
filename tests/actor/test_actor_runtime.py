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

import asyncio
import unittest
from datetime import timedelta
from types import SimpleNamespace
from unittest import mock

from dapr.actor.runtime.config import ActorRuntimeConfig
from dapr.actor.runtime.runtime import ActorRuntime
from dapr.serializers import DefaultJSONSerializer
from tests.actor.fake_actor_classes import (
    FakeMultiInterfacesActor,
    FakeSimpleActor,
    FakeSimpleReminderActor,
    FakeSimpleTimerActor,
)
from tests.actor.utils import _run
from tests.clients.fake_http_server import FakeHttpServer, point_settings_at_http_port


class ActorRuntimeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = FakeHttpServer()
        cls.addClassCleanup(cls.server.shutdown_server)
        cls.server.start()
        point_settings_at_http_port(cls, cls.server.get_port())

    def setUp(self):
        ActorRuntime._actor_managers = {}
        ActorRuntime.set_actor_config(ActorRuntimeConfig())
        ActorRuntime._activation_id_trusted = None
        ActorRuntime._version_lookup = None
        self.addCleanup(setattr, ActorRuntime, '_activation_id_trusted', None)
        self.server.set_response(b'{"runtimeVersion": "1.19.1"}')
        self.addCleanup(self.server.set_response, b'')
        self._serializer = DefaultJSONSerializer()
        _run(ActorRuntime.register_actor(FakeSimpleActor))
        _run(ActorRuntime.register_actor(FakeMultiInterfacesActor))
        _run(ActorRuntime.register_actor(FakeSimpleTimerActor))

    def test_get_registered_actor_types(self):
        actor_types = ActorRuntime.get_registered_actor_types()
        self.assertTrue(actor_types.index('FakeSimpleActor') >= 0)
        self.assertTrue(actor_types.index(FakeMultiInterfacesActor.__name__) >= 0)
        self.assertTrue(actor_types.index(FakeSimpleTimerActor.__name__) >= 0)

    def test_actor_config(self):
        config = ActorRuntime.get_actor_config()

        self.assertTrue(config._drain_rebalanced_actors)
        self.assertEqual(timedelta(hours=1), config._actor_idle_timeout)
        self.assertEqual(timedelta(seconds=30), config._actor_scan_interval)
        self.assertIsNone(config._drain_ongoing_call_timeout)
        self.assertEqual(3, len(config._entities))

        # apply new config
        new_config = ActorRuntimeConfig(
            timedelta(hours=3), timedelta(seconds=10), timedelta(minutes=1), False
        )

        ActorRuntime.set_actor_config(new_config)
        config = ActorRuntime.get_actor_config()

        self.assertFalse(config._drain_rebalanced_actors)
        self.assertEqual(timedelta(hours=3), config._actor_idle_timeout)
        self.assertEqual(timedelta(seconds=10), config._actor_scan_interval)
        self.assertEqual(timedelta(minutes=1), config._drain_ongoing_call_timeout)
        self.assertEqual(3, len(config._entities))

    def test_entities_update(self):
        # Clean up managers
        ActorRuntime._actor_managers = {}
        ActorRuntime.set_actor_config(ActorRuntimeConfig())

        config = ActorRuntime.get_actor_config()
        self.assertFalse(FakeSimpleActor.__name__ in config._entities)

        _run(ActorRuntime.register_actor(FakeSimpleActor))
        config = ActorRuntime.get_actor_config()
        self.assertTrue(FakeSimpleActor.__name__ in config._entities)

    def test_dispatch(self):
        _run(ActorRuntime.register_actor(FakeMultiInterfacesActor))

        request_body = {
            'message': 'hello dapr',
        }

        test_request_body = self._serializer.serialize(request_body)
        response = _run(
            ActorRuntime.dispatch(
                FakeMultiInterfacesActor.__name__, 'test-id', 'ActionMethod', test_request_body
            )
        )

        self.assertEqual(b'"hello dapr"', response)

        _run(ActorRuntime.deactivate(FakeMultiInterfacesActor.__name__, 'test-id'))

        # Ensure test-id is deactivated
        with self.assertRaises(ValueError):
            _run(ActorRuntime.deactivate(FakeMultiInterfacesActor.__name__, 'test-id'))

    def test_fire_timer_success(self):
        # Fire timer
        _run(
            ActorRuntime.fire_timer(
                FakeSimpleTimerActor.__name__,
                'test-id',
                'test_timer',
                '{ "callback": "timer_callback", "data": "timer call" }'.encode('UTF8'),
            )
        )

        manager = ActorRuntime._actor_managers[FakeSimpleTimerActor.__name__]
        actor = manager._active_actors['test-id'].actor
        self.assertTrue(actor.timer_called)

    def test_fire_timer_unregistered(self):
        with self.assertRaises(ValueError):
            _run(
                ActorRuntime.fire_timer(
                    'UnknownType',
                    'test-id',
                    'test_timer',
                    '{ "callback": "timer_callback", "data": "timer call" }'.encode('UTF8'),
                )
            )

    def test_dispatch_new_activation_id_replaces_actor(self):
        actor_type = FakeMultiInterfacesActor.__name__
        request_body = self._serializer.serialize({'message': 'hello dapr'})
        _run(
            ActorRuntime.dispatch(
                actor_type, 'test-id', 'ActionMethod', request_body, activation_id='act-1'
            )
        )
        manager = ActorRuntime._actor_managers[actor_type]
        actor_stale = manager._active_actors['test-id'].actor

        _run(
            ActorRuntime.dispatch(
                actor_type, 'test-id', 'ActionMethod', request_body, activation_id='act-2'
            )
        )

        self.assertIsNot(actor_stale, manager._active_actors['test-id'].actor)
        self.assertTrue(actor_stale.deactivated)
        self.assertEqual('act-2', manager._active_actors['test-id'].activation_id)

    def test_dispatch_same_activation_id_reuses_actor(self):
        actor_type = FakeMultiInterfacesActor.__name__
        request_body = self._serializer.serialize({'message': 'hello dapr'})
        _run(
            ActorRuntime.dispatch(
                actor_type, 'test-id', 'ActionMethod', request_body, activation_id='act-1'
            )
        )
        manager = ActorRuntime._actor_managers[actor_type]
        actor_first = manager._active_actors['test-id'].actor

        _run(
            ActorRuntime.dispatch(
                actor_type, 'test-id', 'ActionMethod', request_body, activation_id='act-1'
            )
        )

        self.assertIs(actor_first, manager._active_actors['test-id'].actor)
        self.assertFalse(actor_first.deactivated)

    def test_fire_timer_new_activation_id_replaces_actor(self):
        actor_type = FakeSimpleTimerActor.__name__
        timer_body = b'{ "callback": "timer_callback", "data": "timer call" }'
        _run(
            ActorRuntime.fire_timer(
                actor_type, 'test-id', 'test_timer', timer_body, activation_id='act-1'
            )
        )
        manager = ActorRuntime._actor_managers[actor_type]
        actor_stale = manager._active_actors['test-id'].actor

        _run(
            ActorRuntime.fire_timer(
                actor_type, 'test-id', 'test_timer', timer_body, activation_id='act-2'
            )
        )

        actor_fresh = manager._active_actors['test-id'].actor
        self.assertIsNot(actor_stale, actor_fresh)
        self.assertTrue(actor_fresh.timer_called)
        self.assertEqual('act-2', manager._active_actors['test-id'].activation_id)

    def test_fire_reminder_new_activation_id_replaces_actor(self):
        _run(ActorRuntime.register_actor(FakeSimpleReminderActor))
        actor_type = FakeSimpleReminderActor.__name__
        reminder_body = self._serializer.serialize(
            {'dueTime': '0h0m1s', 'period': '0h0m1s', 'data': 'cmVtaW5kZXJfc3RhdGU='}
        )
        _run(
            ActorRuntime.fire_reminder(
                actor_type, 'test-id', 'test_reminder', reminder_body, activation_id='act-1'
            )
        )
        manager = ActorRuntime._actor_managers[actor_type]
        actor_stale = manager._active_actors['test-id'].actor

        _run(
            ActorRuntime.fire_reminder(
                actor_type, 'test-id', 'test_reminder', reminder_body, activation_id='act-2'
            )
        )

        self.assertIsNot(actor_stale, manager._active_actors['test-id'].actor)
        self.assertEqual('act-2', manager._active_actors['test-id'].activation_id)

    def test_dispatch_ignores_activation_id_from_old_sidecar(self):
        self.server.set_response(b'{"runtimeVersion": "1.19.0"}')
        actor_type = FakeMultiInterfacesActor.__name__
        request_body = self._serializer.serialize({'message': 'hello dapr'})
        _run(
            ActorRuntime.dispatch(
                actor_type, 'test-id', 'ActionMethod', request_body, activation_id='act-1'
            )
        )
        manager = ActorRuntime._actor_managers[actor_type]
        actor = manager._active_actors['test-id'].actor

        _run(
            ActorRuntime.dispatch(
                actor_type, 'test-id', 'ActionMethod', request_body, activation_id='act-2'
            )
        )

        self.assertIs(actor, manager._active_actors['test-id'].actor)
        self.assertIsNone(manager._active_actors['test-id'].activation_id)
        self.assertEqual('/v1.0/metadata', self.server.request_path())


class ActivationIdGateTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        ActorRuntime._activation_id_trusted = None
        ActorRuntime._version_lookup = None
        self.addCleanup(setattr, ActorRuntime, '_activation_id_trusted', None)
        self.addCleanup(setattr, ActorRuntime, '_version_lookup', None)
        self.client = mock.Mock()
        self.client.get_runtime_version = mock.AsyncMock()
        self.manager = SimpleNamespace(_runtime_ctx=SimpleNamespace(dapr_client=self.client))

    async def _gate(self, activation_id='act-1'):
        return await ActorRuntime._trusted_activation_id(self.manager, activation_id)

    async def test_versions(self):
        cases = {
            '1.19.1': True,
            '1.19.1-rc.1': True,
            '1.19.2': True,
            '1.20.0': True,
            '2.0.0': True,
            '1.19.0': False,
            '1.19.0-rc.2': False,
            '1.18.5': False,
            'edge': False,
            'dev': False,
            '': False,
            'v1.19.1': False,
        }
        for version, trusted in cases.items():
            with self.subTest(version=version):
                ActorRuntime._activation_id_trusted = None
                ActorRuntime._version_lookup = None
                self.client.get_runtime_version.return_value = version
                self.assertEqual('act-1' if trusted else None, await self._gate())

    async def test_result_is_cached(self):
        self.client.get_runtime_version.return_value = '1.19.1'
        self.assertEqual('act-1', await self._gate())
        self.assertEqual('act-2', await self._gate('act-2'))
        self.client.get_runtime_version.assert_awaited_once()

    async def test_no_lookup_without_id(self):
        self.assertIsNone(await self._gate(None))
        self.assertEqual('', await self._gate(''))
        self.client.get_runtime_version.assert_not_awaited()

    async def test_failed_lookup_ignores_id_then_retries(self):
        self.client.get_runtime_version.side_effect = [RuntimeError('down'), '1.19.1']
        self.assertIsNone(await self._gate())
        self.assertIsNone(ActorRuntime._activation_id_trusted)
        self.assertEqual('act-1', await self._gate())
        self.assertEqual(2, self.client.get_runtime_version.await_count)

    async def test_lookup_without_override_ignores_id(self):
        self.client.get_runtime_version.side_effect = NotImplementedError
        self.assertIsNone(await self._gate())

    async def test_concurrent_callers_share_one_lookup(self):
        release = asyncio.Event()

        async def version():
            await release.wait()
            return '1.19.1'

        self.client.get_runtime_version.side_effect = version
        gates = [asyncio.ensure_future(self._gate(f'act-{i}')) for i in range(5)]
        await asyncio.sleep(0)
        release.set()
        self.assertEqual([f'act-{i}' for i in range(5)], await asyncio.gather(*gates))
        self.client.get_runtime_version.assert_awaited_once()
