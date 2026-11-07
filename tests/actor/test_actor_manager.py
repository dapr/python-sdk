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
import threading
import unittest
from datetime import timedelta
from functools import partial
from typing import Awaitable, Callable, Dict, List, Optional, Tuple
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
    _let_pending_tasks_run,
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
        self.assertEqual(test_actor_id, self._manager._active_actors[test_actor_id.id].actor.id)
        self.assertTrue(self._manager._active_actors[test_actor_id.id].actor.activated)
        self.assertFalse(self._manager._active_actors[test_actor_id.id].actor.deactivated)

    def test_deactivate_actor(self):
        """Activate ActorId('2') and deactivate it"""
        test_actor_id = ActorId('2')
        _run(self._manager.activate_actor(test_actor_id))

        # assert
        self.assertEqual(test_actor_id, self._manager._active_actors[test_actor_id.id].actor.id)
        self.assertTrue(self._manager._active_actors[test_actor_id.id].actor.activated)
        self.assertFalse(self._manager._active_actors[test_actor_id.id].actor.deactivated)

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
        actor = manager._active_actors[test_actor_id.id].actor

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
        return self._manager._active_actors[self._actor_id.id].actor

    def _stored_activation_id(self) -> Optional[str]:
        active = self._manager._active_actors.get(self._actor_id.id)
        return active.activation_id if active else None

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
        self.assertEqual('act-other', self._manager._active_actors[other_actor_id.id].activation_id)


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
        actor_stale: AppendActor = self._manager._active_actors[self._actor_id.id].actor
        actor_stale.held = asyncio.Event()
        actor_stale.release = asyncio.Event()
        stale_task = asyncio.ensure_future(stale_call())
        await asyncio.wait_for(actor_stale.held.wait(), 5)

        fresh_task = asyncio.ensure_future(self._append('b', 'act-2'))
        await _let_pending_tasks_run()
        self.assertNotIn(self._actor_id.id, self._manager._active_actors)
        actor_stale.release.set()

        with self.assertRaises(DaprInternalError):
            await asyncio.wait_for(stale_task, 5)
        await asyncio.wait_for(fresh_task, 5)
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
            actor_first: AppendActor = self._manager._active_actors[self._actor_id.id].actor
            actor_first.held = asyncio.Event()
            actor_first.release = asyncio.Event()
            first_task = asyncio.ensure_future(self._append('a', 'act-1'))
            await asyncio.wait_for(actor_first.held.wait(), 5)

            actor_first.held = None
            missing_id_task = asyncio.ensure_future(self._append('b', None))
            await _let_pending_tasks_run()
            actor_first.release.set()
            await asyncio.wait_for(asyncio.gather(first_task, missing_id_task), 5)

        _run(scenario())

        self.assertIn('a', self._stored_items())

    def test_deactivated_during_call_skips_save(self):
        async def scenario() -> None:
            await self._append('x', 'act-1')
            actor_first: AppendActor = self._manager._active_actors[self._actor_id.id].actor
            actor_first.held = asyncio.Event()
            actor_first.release = asyncio.Event()
            first_task = asyncio.ensure_future(self._append('a', 'act-1'))
            await asyncio.wait_for(actor_first.held.wait(), 5)

            deactivation = asyncio.ensure_future(self._manager.deactivate_actor(self._actor_id))
            await _let_pending_tasks_run()
            self.assertNotIn(self._actor_id.id, self._manager._active_actors)
            actor_first.release.set()

            with self.assertRaises(DaprInternalError):
                await asyncio.wait_for(first_task, 5)
            await asyncio.wait_for(deactivation, 5)

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

        actor: PostHookOverrideActor = manager._active_actors['compat'].actor
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


class SaveOnDeactivateActor(AppendActor):
    async def _on_deactivate(self) -> None:
        await self._state_manager.set_state('items', ['deactivated'])
        await self._state_manager.save_state()


class ActorManagerDiscardedSaveTests(unittest.TestCase):
    def setUp(self):
        self._serializer = DefaultJSONSerializer()
        self._client = StoreBackedActorClient()
        type_info = ActorTypeInformation.create(SaveOnDeactivateActor)
        ctx = ActorRuntimeContext(type_info, self._serializer, self._serializer, self._client)
        self._manager = ActorManager(ctx)
        self._actor_id = ActorId('discarded')

    def _stored_items(self) -> object:
        return json.loads(self._client.store['items'])

    async def _append(self, item: str, activation_id: Optional[str]) -> None:
        body = self._serializer.serialize(item)
        await self._manager.dispatch(self._actor_id, 'Append', body, activation_id)

    def test_replaced_actor_cannot_save_from_on_deactivate(self):
        _run(self._append('x', 'act-1'))
        _run(self._append('y', 'act-2'))
        self.assertEqual(['x', 'y'], self._stored_items())

        _run(self._manager.deactivate_actor(self._actor_id))
        self.assertEqual(['deactivated'], self._stored_items())

    def test_replaced_actor_refuses_explicit_save(self):
        async def scenario() -> None:
            await self._append('x', 'act-1')
            actor_stale = self._manager._active_actors[self._actor_id.id].actor
            await self._append('y', 'act-2')
            await actor_stale._state_manager.set_state('items', ['stale'])
            with self.assertRaises(DaprInternalError):
                await actor_stale._state_manager.save_state()

        _run(scenario())
        self.assertEqual(['x', 'y'], self._stored_items())

    def test_new_activation_refuses_the_save_of_a_queued_deactivation(self):
        async def scenario() -> None:
            await self._append('x', 'act-1')
            actor_stale: SaveOnDeactivateActor = self._manager._active_actors[
                self._actor_id.id
            ].actor
            actor_stale.held = asyncio.Event()
            actor_stale.release = asyncio.Event()
            held_task = asyncio.ensure_future(self._append('a', 'act-1'))
            await asyncio.wait_for(actor_stale.held.wait(), 5)
            deactivation = asyncio.ensure_future(self._manager.deactivate_actor(self._actor_id))
            newer_task = asyncio.ensure_future(self._append('b', 'act-2'))
            await _let_pending_tasks_run()

            actor_stale.release.set()
            with self.assertRaises(DaprInternalError):
                await asyncio.wait_for(held_task, 5)
            await asyncio.wait_for(asyncio.gather(deactivation, newer_task), 5)

        with self.assertLogs('dapr.actor.runtime.manager', level='ERROR'):
            _run(scenario())

        self.assertEqual(['x', 'b'], self._stored_items())


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

            newer_task = asyncio.ensure_future(self._append(manager, 'b', 'act-B'))
            await _let_pending_tasks_run()
            release.set()

            with self.assertRaises(DaprInternalError):
                await asyncio.wait_for(late_task, 5)
            await asyncio.wait_for(newer_task, 5)
            self.assertEqual('act-B', manager._active_actors['race'].activation_id)

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

            newer_task = asyncio.ensure_future(self._append(manager, 'b', 'act-B'))
            await _let_pending_tasks_run()
            release.set()

            with self.assertRaises(DaprInternalError):
                await asyncio.wait_for(late_task, 5)
            await asyncio.wait_for(newer_task, 5)

        _run(scenario())

        self.assertEqual(['x', 'init', 'b'], json.loads(self._client.store['items']))

    def test_same_id_call_waits_for_the_running_activation(self):
        manager = self._manager_for(GatedActivateActor)
        self._client.store['items'] = json.dumps(['x']).encode('utf-8')

        async def scenario() -> None:
            GatedActivateActor.activation_started = asyncio.Event()
            release = asyncio.Event()
            GatedActivateActor.activation_release = release
            first_task = asyncio.ensure_future(self._append(manager, 'a', 'act-A'))
            await asyncio.wait_for(GatedActivateActor.activation_started.wait(), 5)

            same_id_task = asyncio.ensure_future(self._append(manager, 'b', 'act-A'))
            await _let_pending_tasks_run()
            release.set()

            await asyncio.wait_for(asyncio.gather(first_task, same_id_task), 5)
            self.assertEqual('act-A', manager._active_actors['race'].activation_id)

        _run(scenario())

        self.assertEqual(['x', 'a', 'b'], json.loads(self._client.store['items']))

    def test_raising_deactivate_on_replace_does_not_fail_new_call(self):
        manager = self._manager_for(RaisingDeactivateActor)

        async def scenario() -> None:
            await self._append(manager, 'a', 'act-A')
            actor_stale = manager._active_actors['race'].actor

            await self._append(manager, 'b', 'act-B')

            self.assertIsNot(actor_stale, manager._active_actors['race'].actor)
            self.assertEqual('act-B', manager._active_actors['race'].activation_id)

        with self.assertLogs('dapr.actor.runtime.manager', level='ERROR'):
            _run(scenario())

        self.assertEqual(['a', 'b'], json.loads(self._client.store['items']))

    def test_old_id_registered_during_reset_fails_new_id_call(self):
        manager = self._manager_for(GatedDeactivateActor)

        async def scenario() -> None:
            await self._append(manager, 'x', 'act-A')
            actor_stale: GatedDeactivateActor = manager._active_actors['race'].actor
            actor_stale.deactivate_started = asyncio.Event()
            actor_stale.deactivate_release = asyncio.Event()
            new_task = asyncio.ensure_future(self._append(manager, 'b', 'act-B'))
            await asyncio.wait_for(actor_stale.deactivate_started.wait(), 5)

            late_task = asyncio.ensure_future(self._append(manager, 'a', 'act-A'))
            await _let_pending_tasks_run()
            actor_stale.deactivate_release.set()

            with self.assertRaises(DaprInternalError):
                await asyncio.wait_for(new_task, 5)
            await asyncio.wait_for(late_task, 5)
            actor_late: GatedDeactivateActor = manager._active_actors['race'].actor
            self.assertEqual(['a'], actor_late.items_appended)
            self.assertEqual('act-A', manager._active_actors['race'].activation_id)

            await self._append(manager, 'c', 'act-B')

            actor_fresh: GatedDeactivateActor = manager._active_actors['race'].actor
            self.assertIsNot(actor_late, actor_fresh)
            self.assertEqual(['c'], actor_fresh.items_appended)
            self.assertEqual('act-B', manager._active_actors['race'].activation_id)

        _run(scenario())

        self.assertEqual(['x', 'a', 'c'], json.loads(self._client.store['items']))


class TurnTrackingActor(AppendActor, Remindable):
    log: Optional[List[str]] = None
    activation_release: Optional[asyncio.Event] = None
    append_pause_seconds = 0.0

    async def append(self, item: str) -> None:
        self._record(f'{item} started')
        if TurnTrackingActor.append_pause_seconds:
            await asyncio.sleep(TurnTrackingActor.append_pause_seconds)
        await super().append(item)
        self._record(f'{item} finished')

    async def _on_activate(self) -> None:
        self._record('activated')
        if TurnTrackingActor.activation_release is not None:
            await TurnTrackingActor.activation_release.wait()

    async def _on_deactivate(self) -> None:
        self._record('deactivated')

    def _record(self, event: str) -> None:
        if TurnTrackingActor.log is not None:
            TurnTrackingActor.log.append(event)


class ActorManagerTurnTests(unittest.TestCase):
    def setUp(self):
        self._serializer = DefaultJSONSerializer()
        self._client = StoreBackedActorClient()
        type_info = ActorTypeInformation.create(TurnTrackingActor)
        ctx = ActorRuntimeContext(type_info, self._serializer, self._serializer, self._client)
        self._manager = ActorManager(ctx)
        self._actor_id = ActorId('turn')
        self._log: List[str] = []
        TurnTrackingActor.log = self._log
        self.addCleanup(setattr, TurnTrackingActor, 'log', None)
        self.addCleanup(setattr, TurnTrackingActor, 'activation_release', None)
        self.addCleanup(setattr, TurnTrackingActor, 'append_pause_seconds', 0.0)

    def _stored_items(self) -> object:
        return json.loads(self._client.store['items'])

    async def _append(
        self,
        item: str,
        activation_id: Optional[str] = None,
        reentrancy_id: Optional[str] = None,
    ) -> None:
        body = self._serializer.serialize(item)
        await self._manager.dispatch(
            self._actor_id, 'Append', body, activation_id, reentrancy_id=reentrancy_id
        )

    async def _hold_append(
        self,
        item: str,
        activation_id: Optional[str] = None,
        reentrancy_id: Optional[str] = None,
    ) -> Tuple['asyncio.Task[None]', TurnTrackingActor]:
        """Activates the actor with an 'x' append, then starts one that waits for ``release``."""
        await self._append('x', activation_id)
        actor: TurnTrackingActor = self._manager._active_actors[self._actor_id.id].actor
        actor.held = asyncio.Event()
        actor.release = asyncio.Event()
        self._log.clear()
        held_task = asyncio.ensure_future(self._append(item, activation_id, reentrancy_id))
        await asyncio.wait_for(actor.held.wait(), 5)
        return held_task, actor

    def test_call_waits_for_the_running_call_to_save(self):
        async def scenario() -> None:
            held_task, actor = await self._hold_append('a')
            next_task = asyncio.ensure_future(self._append('b'))
            await _let_pending_tasks_run()

            self.assertEqual(['a started'], self._log)

            actor.release.set()
            await asyncio.wait_for(asyncio.gather(held_task, next_task), 5)

        _run(scenario())

        self.assertEqual(['a started', 'a finished', 'b started', 'b finished'], self._log)
        self.assertEqual(['x', 'a', 'b'], self._stored_items())

    def test_timer_and_reminder_wait_for_the_running_call(self):
        timer_body = self._serializer.serialize({'callback': 'timer_callback', 'data': 't'})

        async def scenario() -> None:
            held_task, actor = await self._hold_append('a')
            timer_task = asyncio.ensure_future(
                self._manager.fire_timer(self._actor_id, 't1', timer_body)
            )
            reminder_task = asyncio.ensure_future(
                self._manager.fire_reminder(self._actor_id, 'r', REMINDER_BODY)
            )
            await _let_pending_tasks_run()

            self.assertEqual(['a started'], self._log)

            actor.release.set()
            await asyncio.wait_for(asyncio.gather(held_task, timer_task, reminder_task), 5)

        _run(scenario())

        self.assertEqual(['x', 'a', 't', 'r'], self._stored_items())

    def test_deactivation_runs_after_the_running_call(self):
        async def scenario() -> None:
            held_task, actor = await self._hold_append('a')
            deactivation = asyncio.ensure_future(self._manager.deactivate_actor(self._actor_id))
            finished, _ = await asyncio.wait([deactivation], timeout=0.5)

            self.assertEqual(set(), finished)
            self.assertEqual(['a started'], self._log)

            actor.release.set()
            with self.assertRaises(DaprInternalError):
                await asyncio.wait_for(held_task, 5)
            await asyncio.wait_for(deactivation, 5)

        _run(scenario())

        self.assertEqual(['a started', 'a finished', 'deactivated'], self._log)
        self.assertEqual(['x'], self._stored_items())

    def test_deactivation_queued_behind_a_call_leaves_nothing_active(self):
        async def scenario() -> None:
            held_task, actor = await self._hold_append('a')
            queued_task = asyncio.ensure_future(self._append('b'))
            deactivation = asyncio.ensure_future(self._manager.deactivate_actor(self._actor_id))
            await _let_pending_tasks_run()

            actor.release.set()
            with self.assertRaises(DaprInternalError):
                await asyncio.wait_for(held_task, 5)
            await asyncio.wait_for(asyncio.gather(queued_task, deactivation), 5)

        _run(scenario())

        expected_log = [
            'a started',
            'a finished',
            'deactivated',
            'activated',
            'b started',
            'b finished',
            'deactivated',
        ]
        self.assertEqual(expected_log, self._log)
        self.assertNotIn(self._actor_id.id, self._manager._active_actors)
        self.assertEqual(['x', 'b'], self._stored_items())

    def test_dispatches_from_threads_with_their_own_event_loops_take_turns(self):
        TurnTrackingActor.append_pause_seconds = 0.005
        errors: List[BaseException] = []

        def append_items(prefix: str) -> None:
            try:
                for index in range(5):
                    asyncio.run(self._append(f'{prefix}{index}'))
            except BaseException as exception:  # noqa: BLE001
                errors.append(exception)

        threads = [threading.Thread(target=append_items, args=(prefix,)) for prefix in 'abcd']
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(10)

        self.assertEqual([], [thread.name for thread in threads if thread.is_alive()])
        self.assertEqual([], errors)
        appends = [event for event in self._log if event.endswith(('started', 'finished'))]
        appends_started = appends[::2]
        appends_finished = [event.replace('finished', 'started') for event in appends[1::2]]
        self.assertEqual(appends_started, appends_finished)
        self.assertEqual(20, len(self._stored_items()))
        self.assertEqual(1, self._log.count('activated'))
        self.assertEqual({}, self._manager._turn_lock._entries)

    def test_concurrent_first_calls_activate_once(self):
        async def scenario() -> None:
            TurnTrackingActor.activation_release = asyncio.Event()
            first_task = asyncio.ensure_future(self._append('a'))
            second_task = asyncio.ensure_future(self._append('b'))
            await _let_pending_tasks_run()

            TurnTrackingActor.activation_release.set()
            await asyncio.wait_for(asyncio.gather(first_task, second_task), 5)

        _run(scenario())

        self.assertEqual(1, self._log.count('activated'))
        self.assertEqual(['a', 'b'], self._stored_items())

    def test_waiter_superseded_by_a_newer_activation_is_not_run(self):
        async def scenario() -> None:
            held_task, actor = await self._hold_append('a', 'act-1')
            superseded_task = asyncio.ensure_future(self._append('w', 'act-1'))
            newer_task = asyncio.ensure_future(self._append('b', 'act-2'))
            await _let_pending_tasks_run()

            actor.release.set()
            for stale_task in (held_task, superseded_task):
                with self.assertRaises(DaprInternalError):
                    await asyncio.wait_for(stale_task, 5)
            await asyncio.wait_for(newer_task, 5)

        _run(scenario())

        self.assertNotIn('w started', self._log)
        self.assertEqual(1, self._log.count('activated'))
        self.assertEqual(['x', 'b'], self._stored_items())
        self.assertEqual('act-2', self._manager._active_actors[self._actor_id.id].activation_id)
        self.assertEqual({}, self._manager._admissions)

    def test_activation_replaced_while_running_is_deactivated(self):
        async def scenario() -> None:
            TurnTrackingActor.activation_release = asyncio.Event()
            late_task = asyncio.ensure_future(self._append('a', 'act-1'))
            await _let_pending_tasks_run()
            newer_task = asyncio.ensure_future(self._append('b', 'act-2'))
            await _let_pending_tasks_run()

            TurnTrackingActor.activation_release.set()
            with self.assertRaises(DaprInternalError):
                await asyncio.wait_for(late_task, 5)
            await asyncio.wait_for(newer_task, 5)

        _run(scenario())

        expected_log = ['activated', 'deactivated', 'activated', 'b started', 'b finished']
        self.assertEqual(expected_log, self._log)
        self.assertEqual(['b'], self._stored_items())

    def test_reentrant_call_enters_the_running_turn(self):
        async def scenario() -> None:
            held_task, actor = await self._hold_append('a', reentrancy_id='chain')
            actor.held = None

            await asyncio.wait_for(self._append('b', reentrancy_id='chain'), 5)

            self.assertFalse(held_task.done())
            actor.release.set()
            await asyncio.wait_for(held_task, 5)

        _run(scenario())

        self.assertEqual(['a started', 'b started', 'b finished', 'a finished'], self._log)

    def test_call_from_another_chain_waits(self):
        async def scenario() -> None:
            held_task, actor = await self._hold_append('a', reentrancy_id='chain')
            other_task = asyncio.ensure_future(self._append('b', reentrancy_id='other'))
            await _let_pending_tasks_run()

            self.assertEqual(['a started'], self._log)

            actor.release.set()
            await asyncio.wait_for(asyncio.gather(held_task, other_task), 5)

        _run(scenario())

        self.assertEqual(['a started', 'a finished', 'b started', 'b finished'], self._log)

    def test_reentrant_call_after_deactivation_is_not_run(self):
        async def scenario() -> None:
            held_task, actor = await self._hold_append('a', reentrancy_id='chain')
            deactivation = asyncio.ensure_future(self._manager.deactivate_actor(self._actor_id))
            await _let_pending_tasks_run()

            with self.assertRaises(DaprInternalError):
                await asyncio.wait_for(self._append('b', reentrancy_id='chain'), 5)

            actor.release.set()
            with self.assertRaises(DaprInternalError):
                await asyncio.wait_for(held_task, 5)
            await asyncio.wait_for(deactivation, 5)

        _run(scenario())

        self.assertNotIn('b started', self._log)

    def test_deactivation_error_still_reaches_its_caller(self):
        type_info = ActorTypeInformation.create(RaisingDeactivateActor)
        ctx = ActorRuntimeContext(type_info, self._serializer, self._serializer, self._client)
        manager = ActorManager(ctx)
        _run(manager.activate_actor(self._actor_id))

        with self.assertRaises(RuntimeError):
            _run(manager.deactivate_actor(self._actor_id))

        self.assertNotIn(self._actor_id.id, manager._active_actors)

    def test_reentrant_call_with_another_activation_id_does_not_reset(self):
        async def scenario() -> TurnTrackingActor:
            held_task, actor = await self._hold_append('a', 'act-1', reentrancy_id='chain')
            actor.held = None

            await asyncio.wait_for(self._append('b', 'act-2', reentrancy_id='chain'), 5)

            actor.release.set()
            await asyncio.wait_for(held_task, 5)
            return actor

        actor = _run(scenario())

        registered = self._manager._active_actors[self._actor_id.id]
        self.assertIs(actor, registered.actor)
        self.assertEqual('act-1', registered.activation_id)
        self.assertNotIn('deactivated', self._log)
