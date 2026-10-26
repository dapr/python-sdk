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
import json
import unittest
from datetime import timedelta
from functools import partial
from typing import Awaitable, Callable, Dict, List, Optional
from unittest import mock

from dapr.actor.actor_interface import ActorInterface, actormethod
from dapr.actor.id import ActorId
from dapr.actor.runtime._type_information import ActorTypeInformation
from dapr.actor.runtime.actor import Actor
from dapr.actor.runtime.context import ActorRuntimeContext
from dapr.actor.runtime.manager import ActorManager
from dapr.actor.runtime.remindable import Remindable
from dapr.clients.exceptions import DaprInternalError
from dapr.serializers import DefaultJSONSerializer
from tests.actor.fake_actor_classes import (
    FakeMultiInterfacesActor,
    FakeSimpleActor,
    FakeSimpleReminderActor,
    FakeSimpleTimerActor,
)
from tests.actor.fake_client import FakeDaprActorClient
from tests.actor.utils import (
    _async_mock,
    _run,
)


class ActorManagerTests(unittest.TestCase):
    def setUp(self):
        self._test_type_info = ActorTypeInformation.create(FakeMultiInterfacesActor)
        self._serializer = DefaultJSONSerializer()

        self._fake_client = FakeDaprActorClient
        self._runtime_ctx = ActorRuntimeContext(
            self._test_type_info, self._serializer, self._serializer, self._fake_client
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

    def test_deactivate_actor(self):
        """Activate ActorId('2') and deactivate it"""
        test_actor_id = ActorId('2')
        _run(self._manager.activate_actor(test_actor_id))

        # assert
        self.assertEqual(test_actor_id, self._manager._active_actors[test_actor_id.id].id)
        self.assertTrue(self._manager._active_actors[test_actor_id.id].activated)
        self.assertFalse(self._manager._active_actors[test_actor_id.id].deactivated)

        _run(self._manager.deactivate_actor(test_actor_id))
        self.assertIsNone(self._manager._active_actors.get(test_actor_id.id))

    def test_dispatch_success(self):
        """dispatch ActionMethod"""
        test_actor_id = ActorId('dispatch')
        _run(self._manager.activate_actor(test_actor_id))

        request_body = {
            'message': 'hello dapr',
        }

        test_request_body = self._serializer.serialize(request_body)
        response = _run(self._manager.dispatch(test_actor_id, 'ActionMethod', test_request_body))
        self.assertEqual(b'"hello dapr"', response)


class ActorManagerReminderTests(unittest.TestCase):
    def setUp(self):
        self._serializer = DefaultJSONSerializer()
        self._fake_client = FakeDaprActorClient

        self._test_reminder_req = self._serializer.serialize(
            {
                'name': 'test_reminder',
                'dueTime': timedelta(seconds=1),
                'period': timedelta(seconds=1),
                'ttl': timedelta(seconds=1),
                'data': 'cmVtaW5kZXJfc3RhdGU=',
            }
        )

    def test_fire_reminder_for_non_reminderable(self):
        test_type_info = ActorTypeInformation.create(FakeSimpleActor)
        ctx = ActorRuntimeContext(
            test_type_info, self._serializer, self._serializer, self._fake_client
        )
        manager = ActorManager(ctx)
        with self.assertRaises(ValueError):
            _run(manager.fire_reminder(ActorId('testid'), 'test_reminder', self._test_reminder_req))

    def test_fire_reminder_success(self):
        test_actor_id = ActorId('testid')
        test_type_info = ActorTypeInformation.create(FakeSimpleReminderActor)
        ctx = ActorRuntimeContext(
            test_type_info, self._serializer, self._serializer, self._fake_client
        )
        manager = ActorManager(ctx)
        _run(manager.activate_actor(test_actor_id))
        _run(manager.fire_reminder(test_actor_id, 'test_reminder', self._test_reminder_req))

    def test_fire_reminder_non_dict_payload_is_ignored(self):
        test_actor_id = ActorId('testid')
        test_type_info = ActorTypeInformation.create(FakeSimpleReminderActor)
        ctx = ActorRuntimeContext(
            test_type_info, self._serializer, self._serializer, self._fake_client
        )
        manager = ActorManager(ctx)
        _run(manager.activate_actor(test_actor_id))
        # A non-dict payload (e.g. JSON null) should be ignored, not raise.
        _run(manager.fire_reminder(test_actor_id, 'test_reminder', b'null'))


class ActorManagerTimerTests(unittest.TestCase):
    def setUp(self):
        self._serializer = DefaultJSONSerializer()

        self._fake_client = FakeDaprActorClient

    @mock.patch(
        'tests.actor.fake_client.FakeDaprActorClient.invoke_method',
        new=_async_mock(return_value=b'"expected_response"'),
    )
    @mock.patch('tests.actor.fake_client.FakeDaprActorClient.register_timer', new=_async_mock())
    def test_fire_timer_success(self):
        test_actor_id = ActorId('testid')
        test_type_info = ActorTypeInformation.create(FakeSimpleTimerActor)
        ctx = ActorRuntimeContext(
            test_type_info, self._serializer, self._serializer, self._fake_client
        )
        manager = ActorManager(ctx)

        _run(manager.activate_actor(test_actor_id))
        actor = manager._active_actors.get(test_actor_id.id, None)

        # Setup timer
        _run(
            actor.register_timer(
                'test_timer',
                actor.timer_callback,
                'timer call',
                timedelta(seconds=1),
                timedelta(seconds=1),
                timedelta(seconds=1),
            )
        )

        # Fire timer
        _run(
            manager.fire_timer(
                test_actor_id,
                'test_timer',
                '{ "callback": "timer_callback", "data": "timer call" }'.encode('UTF8'),
            )
        )

        self.assertTrue(actor.timer_called)


class ActivationTrackingActorInterface(ActorInterface):
    @actormethod(name='Remember')
    async def remember(self, value: object) -> None: ...

    @actormethod(name='Recall')
    async def recall(self) -> object: ...


class ActivationTrackingActor(Actor, ActivationTrackingActorInterface, Remindable):
    def __init__(self, ctx, actor_id):
        super().__init__(ctx, actor_id)
        self.activate_calls = 0
        self.deactivate_calls = 0
        self.reminders_received: List[str] = []
        self.timer_data_received: List[object] = []

    async def remember(self, value: object) -> None:
        await self._state_manager.set_state('value', value)

    async def recall(self) -> object:
        return await self._state_manager.get_state('value')

    async def timer_callback(self, data: object) -> None:
        self.timer_data_received.append(data)

    async def receive_reminder(
        self,
        name: str,
        state: bytes,
        due_time: timedelta,
        period: timedelta,
        ttl: Optional[timedelta],
    ) -> None:
        self.reminders_received.append(name)

    async def _on_activate(self) -> None:
        self.activate_calls += 1

    async def _on_deactivate(self) -> None:
        self.deactivate_calls += 1


STORED_VALUE = 'expected_response'
REMINDER_BODY = DefaultJSONSerializer().serialize(
    {'dueTime': '0h0m1s', 'period': '0h0m1s', 'data': 'cmVtaW5kZXJfc3RhdGU='}
)
TIMER_BODY = b'{ "callback": "timer_callback", "data": "timer call" }'


class ActorManagerActivationIdTests(unittest.TestCase):
    def setUp(self):
        self._serializer = DefaultJSONSerializer()
        type_info = ActorTypeInformation.create(ActivationTrackingActor)
        ctx = ActorRuntimeContext(
            type_info, self._serializer, self._serializer, FakeDaprActorClient()
        )
        self._manager = ActorManager(ctx)
        self._actor_id = ActorId('activation')

    def _remember(self, value: str, activation_id: Optional[str]) -> None:
        body = self._serializer.serialize(value)
        _run(self._manager.dispatch(self._actor_id, 'Remember', body, activation_id))

    def _recall(self, activation_id: Optional[str]) -> object:
        response = _run(self._manager.dispatch(self._actor_id, 'Recall', b'', activation_id))
        return self._serializer.deserialize(response)

    def _active_actor(self) -> ActivationTrackingActor:
        return self._manager._active_actors[self._actor_id.id]

    def _stored_activation_id(self) -> Optional[str]:
        return self._manager._activation_ids.get(self._actor_id.id)

    def test_first_call_stores_activation_id(self):
        self._remember('cached', 'act-1')

        self.assertEqual('act-1', self._stored_activation_id())
        self.assertEqual(1, self._active_actor().activate_calls)

    def test_same_activation_id_reuses_actor_and_cache(self):
        self._remember('cached', 'act-1')
        actor_first = self._active_actor()

        recalled = self._recall('act-1')

        self.assertIs(actor_first, self._active_actor())
        self.assertEqual('cached', recalled)
        self.assertEqual(0, actor_first.deactivate_calls)

    def test_new_activation_id_replaces_actor_and_drops_cache(self):
        self._remember('cached', 'act-1')
        actor_stale = self._active_actor()

        recalled = self._recall('act-2')

        actor_fresh = self._active_actor()
        self.assertIsNot(actor_stale, actor_fresh)
        self.assertEqual(1, actor_stale.deactivate_calls)
        self.assertEqual({}, actor_stale._state_manager._default_state_change_tracker)
        self.assertEqual(1, actor_fresh.activate_calls)
        self.assertEqual(0, actor_fresh.deactivate_calls)
        self.assertEqual(STORED_VALUE, recalled)
        self.assertEqual('act-2', self._stored_activation_id())

    def test_missing_activation_id_never_resets(self):
        self._remember('cached', 'act-1')
        actor_first = self._active_actor()

        recalled_none = self._recall(None)
        recalled_empty = self._recall('')

        self.assertIs(actor_first, self._active_actor())
        self.assertEqual('cached', recalled_none)
        self.assertEqual('cached', recalled_empty)
        self.assertEqual(0, actor_first.deactivate_calls)
        self.assertEqual('act-1', self._stored_activation_id())

    def test_without_activation_ids_actor_is_reused(self):
        self._remember('cached', None)
        actor_first = self._active_actor()

        recalled = self._recall(None)

        self.assertIs(actor_first, self._active_actor())
        self.assertEqual('cached', recalled)
        self.assertIsNone(self._stored_activation_id())

    def test_stored_empty_then_activation_id_resets(self):
        self._remember('cached', None)
        actor_stale = self._active_actor()

        recalled = self._recall('act-1')

        self.assertIsNot(actor_stale, self._active_actor())
        self.assertEqual(1, actor_stale.deactivate_calls)
        self.assertEqual(STORED_VALUE, recalled)
        self.assertEqual('act-1', self._stored_activation_id())

    def test_activate_actor_without_id_then_activation_id_resets(self):
        _run(self._manager.activate_actor(self._actor_id))
        actor_stale = self._active_actor()

        self._recall('act-1')

        self.assertIsNot(actor_stale, self._active_actor())
        self.assertEqual(1, actor_stale.deactivate_calls)

    def test_deactivate_actor_clears_activation_id(self):
        self._remember('cached', 'act-1')
        actor_first = self._active_actor()

        _run(self._manager.deactivate_actor(self._actor_id))

        self.assertIsNone(self._stored_activation_id())
        self.assertEqual(1, actor_first.deactivate_calls)

        self._recall('act-1')

        self.assertIsNot(actor_first, self._active_actor())
        self.assertEqual(1, actor_first.deactivate_calls)
        self.assertEqual('act-1', self._stored_activation_id())

    def test_reminder_same_activation_id_reuses_actor(self):
        self._remember('cached', 'act-1')
        actor_first = self._active_actor()

        _run(self._manager.fire_reminder(self._actor_id, 'r1', REMINDER_BODY, 'act-1'))

        self.assertIs(actor_first, self._active_actor())
        self.assertEqual(['r1'], actor_first.reminders_received)
        self.assertEqual(0, actor_first.deactivate_calls)

    def test_reminder_new_activation_id_replaces_actor(self):
        self._remember('cached', 'act-1')
        actor_stale = self._active_actor()

        _run(self._manager.fire_reminder(self._actor_id, 'r1', REMINDER_BODY, 'act-2'))

        actor_fresh = self._active_actor()
        self.assertIsNot(actor_stale, actor_fresh)
        self.assertEqual(1, actor_stale.deactivate_calls)
        self.assertEqual([], actor_stale.reminders_received)
        self.assertEqual(['r1'], actor_fresh.reminders_received)
        self.assertEqual('act-2', self._stored_activation_id())
        self.assertEqual(STORED_VALUE, self._recall('act-2'))

    def test_reminder_missing_activation_id_never_resets(self):
        self._remember('cached', 'act-1')
        actor_first = self._active_actor()

        _run(self._manager.fire_reminder(self._actor_id, 'r1', REMINDER_BODY))

        self.assertIs(actor_first, self._active_actor())
        self.assertEqual(['r1'], actor_first.reminders_received)

    def test_timer_same_activation_id_reuses_actor(self):
        self._remember('cached', 'act-1')
        actor_first = self._active_actor()

        _run(self._manager.fire_timer(self._actor_id, 't1', TIMER_BODY, 'act-1'))

        self.assertIs(actor_first, self._active_actor())
        self.assertEqual(['timer call'], actor_first.timer_data_received)
        self.assertEqual(0, actor_first.deactivate_calls)

    def test_timer_new_activation_id_replaces_actor(self):
        self._remember('cached', 'act-1')
        actor_stale = self._active_actor()

        _run(self._manager.fire_timer(self._actor_id, 't1', TIMER_BODY, 'act-2'))

        actor_fresh = self._active_actor()
        self.assertIsNot(actor_stale, actor_fresh)
        self.assertEqual(1, actor_stale.deactivate_calls)
        self.assertEqual([], actor_stale.timer_data_received)
        self.assertEqual(['timer call'], actor_fresh.timer_data_received)
        self.assertEqual('act-2', self._stored_activation_id())
        self.assertEqual(STORED_VALUE, self._recall('act-2'))

    def test_timer_missing_activation_id_never_resets(self):
        self._remember('cached', 'act-1')
        actor_first = self._active_actor()

        _run(self._manager.fire_timer(self._actor_id, 't1', TIMER_BODY, ''))

        self.assertIs(actor_first, self._active_actor())
        self.assertEqual(['timer call'], actor_first.timer_data_received)

    def test_activation_ids_are_tracked_per_actor(self):
        other_actor_id = ActorId('other')
        self._remember('cached', 'act-1')
        actor_first = self._active_actor()

        _run(self._manager.dispatch(other_actor_id, 'Recall', b'', 'act-other'))

        self.assertIs(actor_first, self._active_actor())
        self.assertEqual('act-1', self._stored_activation_id())
        self.assertEqual('act-other', self._manager._activation_ids[other_actor_id.id])


class StoreBackedActorClient(FakeDaprActorClient):
    def __init__(self):
        self.store: Dict[str, bytes] = {}

    async def get_state(self, actor_type: str, actor_id: str, name: str) -> bytes:
        return self.store.get(name, b'')

    async def save_state_transactionally(self, actor_type: str, actor_id: str, data: bytes) -> None:
        for operation in json.loads(data):
            key = operation['request']['key']
            if operation['operation'] == 'delete':
                self.store.pop(key, None)
                continue
            self.store[key] = json.dumps(operation['request']['value']).encode('utf-8')


class AppendActorInterface(ActorInterface):
    @actormethod(name='Append')
    async def append(self, item: str) -> None: ...


class AppendActor(Actor, AppendActorInterface, Remindable):
    def __init__(self, ctx, actor_id):
        super().__init__(ctx, actor_id)
        self.held: Optional[asyncio.Event] = None
        self.release: Optional[asyncio.Event] = None

    async def append(self, item: str) -> None:
        items_found, items = await self._state_manager.try_get_state('items')
        items_current = items if items_found else []
        if self.held is not None and self.release is not None:
            self.held.set()
            await self.release.wait()
        await self._state_manager.set_state('items', items_current + [item])

    async def timer_callback(self, item: str) -> None:
        await self.append(item)

    async def failing_timer_callback(self, item: str) -> None:
        await self.append(item)
        raise RuntimeError('timer failed')

    async def receive_reminder(
        self,
        name: str,
        state: bytes,
        due_time: timedelta,
        period: timedelta,
        ttl: Optional[timedelta],
    ) -> None:
        await self.append(name)


class ActorManagerReplacedSaveTests(unittest.TestCase):
    def setUp(self):
        self._serializer = DefaultJSONSerializer()
        self._client = StoreBackedActorClient()
        type_info = ActorTypeInformation.create(AppendActor)
        ctx = ActorRuntimeContext(type_info, self._serializer, self._serializer, self._client)
        self._manager = ActorManager(ctx)
        self._actor_id = ActorId('replaced')

    def _stored_items(self) -> object:
        return json.loads(self._client.store['items'])

    async def _append(self, item: str, activation_id: Optional[str]) -> None:
        body = self._serializer.serialize(item)
        await self._manager.dispatch(self._actor_id, 'Append', body, activation_id)

    async def _run_replaced_during(self, stale_call: Callable[[], Awaitable[None]]) -> None:
        await self._append('x', 'act-1')
        actor_stale: AppendActor = self._manager._active_actors[self._actor_id.id]
        actor_stale.held = asyncio.Event()
        actor_stale.release = asyncio.Event()
        stale_task = asyncio.ensure_future(stale_call())
        await asyncio.wait_for(actor_stale.held.wait(), 5)

        await self._append('b', 'act-2')
        actor_stale.release.set()

        with self.assertRaises(DaprInternalError):
            await asyncio.wait_for(stale_task, 5)
        self.assertEqual(['x', 'b'], self._stored_items())

    def test_replaced_method_call_skips_save(self):
        _run(self._run_replaced_during(lambda: self._append('a', 'act-1')))

    def test_replaced_timer_skips_save(self):
        timer_body = self._serializer.serialize({'callback': 'timer_callback', 'data': 'a'})
        stale_call = partial(self._manager.fire_timer, self._actor_id, 't1', timer_body, 'act-1')

        _run(self._run_replaced_during(stale_call))

    def test_replaced_reminder_skips_save(self):
        stale_call = partial(
            self._manager.fire_reminder, self._actor_id, 'a', REMINDER_BODY, 'act-1'
        )

        _run(self._run_replaced_during(stale_call))

    def test_raising_timer_skips_save(self):
        _run(self._append('x', 'act-1'))
        timer_body = self._serializer.serialize({'callback': 'failing_timer_callback', 'data': 'a'})

        with self.assertRaises(RuntimeError):
            _run(self._manager.fire_timer(self._actor_id, 't1', timer_body, 'act-1'))

        self.assertEqual(['x'], self._stored_items())

    def test_replaced_by_missing_id_call_still_saves(self):
        async def scenario() -> None:
            await self._append('x', 'act-1')
            actor_first: AppendActor = self._manager._active_actors[self._actor_id.id]
            actor_first.held = asyncio.Event()
            actor_first.release = asyncio.Event()
            first_task = asyncio.ensure_future(self._append('a', 'act-1'))
            await asyncio.wait_for(actor_first.held.wait(), 5)

            actor_first.held = None
            await self._append('b', None)
            actor_first.release.set()
            await asyncio.wait_for(first_task, 5)

        _run(scenario())

        self.assertIn('a', self._stored_items())

    def test_deactivated_during_call_skips_save(self):
        async def scenario() -> None:
            await self._append('x', 'act-1')
            actor_first: AppendActor = self._manager._active_actors[self._actor_id.id]
            actor_first.held = asyncio.Event()
            actor_first.release = asyncio.Event()
            first_task = asyncio.ensure_future(self._append('a', 'act-1'))
            await asyncio.wait_for(actor_first.held.wait(), 5)

            await self._manager.deactivate_actor(self._actor_id)
            actor_first.release.set()

            with self.assertRaises(DaprInternalError):
                await asyncio.wait_for(first_task, 5)

        _run(scenario())

        self.assertEqual(['x'], self._stored_items())


class PostHookOverrideActor(AppendActor):
    def __init__(self, ctx, actor_id):
        super().__init__(ctx, actor_id)
        self.post_internal_calls: List[str] = []

    async def _on_post_actor_method_internal(self, method_context, before_save=None) -> None:
        self.post_internal_calls.append(method_context.method_name)
        await super()._on_post_actor_method_internal(method_context, before_save)


class ActorInternalHookCompatTests(unittest.TestCase):
    def setUp(self):
        self._serializer = DefaultJSONSerializer()
        self._client = StoreBackedActorClient()

    def _ctx(self, actor_class: type) -> ActorRuntimeContext:
        type_info = ActorTypeInformation.create(actor_class)
        return ActorRuntimeContext(type_info, self._serializer, self._serializer, self._client)

    def test_on_activate_internal_without_can_save_saves(self):
        actor = GatedActivateWriteActor(self._ctx(GatedActivateWriteActor), ActorId('compat'))

        _run(actor._on_activate_internal())

        self.assertEqual(['init'], json.loads(self._client.store['items']))

    def test_manager_calls_overridden_post_actor_method_internal(self):
        manager = ActorManager(self._ctx(PostHookOverrideActor))
        body = self._serializer.serialize('a')

        _run(manager.dispatch(ActorId('compat'), 'Append', body, 'act-1'))

        actor: PostHookOverrideActor = manager._active_actors['compat']
        self.assertEqual(['Append'], actor.post_internal_calls)
        self.assertEqual(['a'], json.loads(self._client.store['items']))


class GatedActivateActor(AppendActor):
    activation_started: Optional[asyncio.Event] = None
    activation_release: Optional[asyncio.Event] = None

    async def _on_activate(self) -> None:
        await self._state_manager.try_get_state('items')
        release = GatedActivateActor.activation_release
        if release is None:
            return
        GatedActivateActor.activation_release = None
        if GatedActivateActor.activation_started is not None:
            GatedActivateActor.activation_started.set()
        await release.wait()


class GatedActivateWriteActor(AppendActor):
    async def _on_activate(self) -> None:
        items_found, items = await self._state_manager.try_get_state('items')
        release = GatedActivateActor.activation_release
        if release is not None:
            GatedActivateActor.activation_release = None
            if GatedActivateActor.activation_started is not None:
                GatedActivateActor.activation_started.set()
            await release.wait()
        await self._state_manager.set_state('items', (items if items_found else []) + ['init'])


class GatedDeactivateActor(AppendActor):
    def __init__(self, ctx, actor_id):
        super().__init__(ctx, actor_id)
        self.deactivate_started: Optional[asyncio.Event] = None
        self.deactivate_release: Optional[asyncio.Event] = None
        self.items_appended: List[str] = []

    async def append(self, item: str) -> None:
        self.items_appended.append(item)
        await super().append(item)

    async def _on_deactivate(self) -> None:
        if self.deactivate_started is not None and self.deactivate_release is not None:
            self.deactivate_started.set()
            await self.deactivate_release.wait()


class RaisingDeactivateActor(AppendActor):
    async def _on_deactivate(self) -> None:
        raise RuntimeError('deactivate failed')


class ActorManagerConcurrentActivationTests(unittest.TestCase):
    def _manager_for(self, actor_class: type) -> ActorManager:
        serializer = DefaultJSONSerializer()
        self._serializer = serializer
        self._client = StoreBackedActorClient()
        type_info = ActorTypeInformation.create(actor_class)
        ctx = ActorRuntimeContext(type_info, serializer, serializer, self._client)
        return ActorManager(ctx)

    async def _append(self, manager: ActorManager, item: str, activation_id: Optional[str]) -> None:
        body = self._serializer.serialize(item)
        await manager.dispatch(ActorId('race'), 'Append', body, activation_id)

    def tearDown(self):
        GatedActivateActor.activation_started = None
        GatedActivateActor.activation_release = None

    def test_late_activation_does_not_overwrite_newer_activation(self):
        manager = self._manager_for(GatedActivateActor)
        self._client.store['items'] = json.dumps(['x']).encode('utf-8')

        async def scenario() -> None:
            GatedActivateActor.activation_started = asyncio.Event()
            release = asyncio.Event()
            GatedActivateActor.activation_release = release
            late_task = asyncio.ensure_future(self._append(manager, 'a', 'act-A'))
            await asyncio.wait_for(GatedActivateActor.activation_started.wait(), 5)

            await self._append(manager, 'b', 'act-B')
            actor_newer = manager._active_actors['race']
            release.set()

            with self.assertRaises(DaprInternalError):
                await asyncio.wait_for(late_task, 5)
            self.assertIs(actor_newer, manager._active_actors['race'])
            self.assertEqual('act-B', manager._activation_ids['race'])

        _run(scenario())

        self.assertEqual(['x', 'b'], json.loads(self._client.store['items']))

    def test_late_activation_save_does_not_overwrite_newer_activation(self):
        manager = self._manager_for(GatedActivateWriteActor)
        self._client.store['items'] = json.dumps(['x']).encode('utf-8')

        async def scenario() -> None:
            GatedActivateActor.activation_started = asyncio.Event()
            release = asyncio.Event()
            GatedActivateActor.activation_release = release
            late_task = asyncio.ensure_future(self._append(manager, 'a', 'act-A'))
            await asyncio.wait_for(GatedActivateActor.activation_started.wait(), 5)

            await self._append(manager, 'b', 'act-B')
            release.set()

            with self.assertRaises(DaprInternalError):
                await asyncio.wait_for(late_task, 5)

        _run(scenario())

        self.assertEqual(['x', 'init', 'b'], json.loads(self._client.store['items']))

    def test_late_activation_with_same_id_reuses_winner(self):
        manager = self._manager_for(GatedActivateActor)
        self._client.store['items'] = json.dumps(['x']).encode('utf-8')

        async def scenario() -> None:
            GatedActivateActor.activation_started = asyncio.Event()
            release = asyncio.Event()
            GatedActivateActor.activation_release = release
            late_task = asyncio.ensure_future(self._append(manager, 'a', 'act-A'))
            await asyncio.wait_for(GatedActivateActor.activation_started.wait(), 5)

            await self._append(manager, 'b', 'act-A')
            actor_winner = manager._active_actors['race']
            release.set()

            await asyncio.wait_for(late_task, 5)
            self.assertIs(actor_winner, manager._active_actors['race'])
            self.assertEqual('act-A', manager._activation_ids['race'])

        _run(scenario())

        self.assertEqual(['x', 'b', 'a'], json.loads(self._client.store['items']))

    def test_raising_deactivate_on_replace_does_not_fail_new_call(self):
        manager = self._manager_for(RaisingDeactivateActor)

        async def scenario() -> None:
            await self._append(manager, 'a', 'act-A')
            actor_stale = manager._active_actors['race']

            await self._append(manager, 'b', 'act-B')

            self.assertIsNot(actor_stale, manager._active_actors['race'])
            self.assertEqual('act-B', manager._activation_ids['race'])

        with self.assertLogs('dapr.actor.runtime.manager', level='ERROR'):
            _run(scenario())

        self.assertEqual(['a', 'b'], json.loads(self._client.store['items']))

    def test_old_id_registered_during_reset_fails_new_id_call(self):
        manager = self._manager_for(GatedDeactivateActor)

        async def scenario() -> None:
            await self._append(manager, 'x', 'act-A')
            actor_stale: GatedDeactivateActor = manager._active_actors['race']
            actor_stale.deactivate_started = asyncio.Event()
            actor_stale.deactivate_release = asyncio.Event()
            new_task = asyncio.ensure_future(self._append(manager, 'b', 'act-B'))
            await asyncio.wait_for(actor_stale.deactivate_started.wait(), 5)

            await self._append(manager, 'a', 'act-A')
            actor_late: GatedDeactivateActor = manager._active_actors['race']
            actor_stale.deactivate_release.set()

            with self.assertRaises(DaprInternalError):
                await asyncio.wait_for(new_task, 5)
            self.assertEqual(['a'], actor_late.items_appended)
            self.assertEqual('act-A', manager._activation_ids['race'])

            await self._append(manager, 'c', 'act-B')

            actor_fresh: GatedDeactivateActor = manager._active_actors['race']
            self.assertIsNot(actor_late, actor_fresh)
            self.assertEqual(['c'], actor_fresh.items_appended)
            self.assertEqual('act-B', manager._activation_ids['race'])

        _run(scenario())

        self.assertEqual(['x', 'a', 'c'], json.loads(self._client.store['items']))
