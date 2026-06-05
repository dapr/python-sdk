# -*- coding: utf-8 -*-

"""
Copyright 2026 The Dapr Authors
Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at
    http://www.apache.org/licenses/LICENSE-2.0
Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.

Tests for ActorGrpcHost against a scripted fake daprd.

A real ActorGrpcHost connects to FakeDaprSidecar, whose
SubscribeActorEventsAlpha1 servicer follows one plan per connection (see
tests/clients/fake_dapr_server.py): it acks the registration, pushes the
plan's callback messages round by round (reading one correlated reply per
pushed message), and then holds the stream open, closes it, or aborts it to
simulate a sidecar drop. Tests script a plan with ``_plan``/``_serve_callbacks``
and assert on the replies the host sent back. This mirrors how the streaming
PubSub clients are tested in tests/clients/test_dapr_grpc_client*.py.
"""

import asyncio
import base64
import json
import time
import unittest
from datetime import timedelta
from typing import Optional
from unittest import mock

from google.protobuf import any_pb2, wrappers_pb2
from grpc import StatusCode  # type: ignore[attr-defined]
from grpc.aio import AioRpcError

from dapr.actor.actor_interface import ActorInterface, actormethod
from dapr.actor.runtime.actor import Actor
from dapr.actor.runtime.config import ActorRuntimeConfig
from dapr.actor.runtime.grpc_host import ActorGrpcHost
from dapr.actor.runtime.reentrancy_context import reentrancy_ctx
from dapr.actor.runtime.remindable import Remindable
from dapr.actor.runtime.runtime import ActorRuntime
from dapr.proto import api_v1
from tests.clients.fake_dapr_server import FakeDaprSidecar

GRPC_PORT = 50010
HTTP_PORT = 3510


class HostTestActorInterface(ActorInterface):
    @actormethod(name='GetName')
    async def get_name(self) -> dict: ...

    @actormethod(name='Echo')
    async def echo(self, data: object) -> object: ...

    @actormethod(name='SaveData')
    async def save_data(self, data: object) -> None: ...

    @actormethod(name='WhoAmI')
    async def who_am_i(self) -> Optional[str]: ...

    @actormethod(name='Fail')
    async def fail(self) -> None: ...

    @actormethod(name='FailWithValueError')
    async def fail_with_value_error(self) -> None: ...


class HostTestActor(Actor, HostTestActorInterface, Remindable):
    """Records every callback so tests can assert against real dispatches."""

    reminders_fired: list = []
    timers_fired: list = []
    deactivated_ids: list = []

    async def get_name(self) -> dict:
        return {'name': 'HostTestActor'}

    async def echo(self, data: object) -> object:
        return data

    async def save_data(self, data: object) -> None:
        await self._state_manager.set_state('mydata', data)
        await self._state_manager.save_state()

    async def who_am_i(self) -> Optional[str]:
        return reentrancy_ctx.get()

    async def fail(self) -> None:
        raise RuntimeError('handler exploded')

    async def fail_with_value_error(self) -> None:
        raise ValueError('bad user input')

    async def receive_reminder(
        self,
        name: str,
        state: bytes,
        due_time: timedelta,
        period: timedelta,
        ttl: Optional[timedelta],
    ) -> None:
        HostTestActor.reminders_fired.append((name, state))

    async def timer_callback(self, state) -> None:
        HostTestActor.timers_fired.append(state)

    async def _on_deactivate(self) -> None:
        HostTestActor.deactivated_ids.append(self.id.id)


def _plan(*rounds, end='hold', reject=None):
    """Builds one connection script for the fake daprd's actor event stream.

    Args:
        rounds: lists of callback messages pushed together; the fake server
            reads one correlated reply per message before the next round.
        end: what happens after the rounds — 'hold' keeps the stream open,
            'abort' drops it with UNAVAILABLE, 'eof' closes it cleanly.
        reject: when set, the connection is rejected with this status code
            before the registration is acked.
    """
    if reject is not None:
        return {'reject': reject}
    return {'rounds': list(rounds), 'end': end}


def _invoke_message(request_id, method, data=b'', actor_type='HostTestActor', metadata=None):
    """Builds the invoke callback daprd pushes for an actor method call."""
    invoke_request = api_v1.SubscribeActorEventsResponseInvokeRequestAlpha1(
        id=request_id,
        actor_type=actor_type,
        actor_id='a1',
        method=method,
        data=data,
        metadata=metadata or {},
    )
    return api_v1.SubscribeActorEventsResponseAlpha1(invoke_request=invoke_request)


def _packed_bytes_value(value: bytes) -> any_pb2.Any:
    """Wraps payload bytes in a BytesValue-packed Any, the way daprd stores
    reminder and timer data."""
    packed = any_pb2.Any()
    packed.Pack(wrappers_pb2.BytesValue(value=value))
    return packed


def _reminder_message(request_id, name, state: bytes):
    """Builds the reminder-fire callback for a reminder registered with `state`."""
    json_value = json.dumps(base64.b64encode(state).decode('utf-8')).encode('utf-8')
    reminder_request = api_v1.SubscribeActorEventsResponseReminderRequestAlpha1(
        id=request_id,
        actor_type='HostTestActor',
        actor_id='a1',
        name=name,
        due_time='0h0m5s',
        period='0h0m10s',
        data=_packed_bytes_value(json_value),
    )
    return api_v1.SubscribeActorEventsResponseAlpha1(reminder_request=reminder_request)


def _timer_message(request_id, name, callback, data_json: bytes):
    """Builds the timer-fire callback for a timer with a JSON data payload."""
    timer_request = api_v1.SubscribeActorEventsResponseTimerRequestAlpha1(
        id=request_id,
        actor_type='HostTestActor',
        actor_id='a1',
        name=name,
        due_time='0h0m5s',
        period='0h0m10s',
        callback=callback,
        data=_packed_bytes_value(data_json),
    )
    return api_v1.SubscribeActorEventsResponseAlpha1(timer_request=timer_request)


def _deactivate_message(request_id, actor_id='a1'):
    """Builds the deactivate callback for an actor instance."""
    deactivate_request = api_v1.SubscribeActorEventsResponseDeactivateRequestAlpha1(
        id=request_id, actor_type='HostTestActor', actor_id=actor_id
    )
    return api_v1.SubscribeActorEventsResponseAlpha1(deactivate_request=deactivate_request)


class ActorGrpcHostTests(unittest.IsolatedAsyncioTestCase):
    """Each test isolates the process-global ActorRuntime state in setUp and
    restores it in asyncTearDown, since the host and the runtime share it."""

    @classmethod
    def setUpClass(cls):
        cls._fake_dapr_server = FakeDaprSidecar(grpc_port=GRPC_PORT, http_port=HTTP_PORT)
        cls._fake_dapr_server.start()

    @classmethod
    def tearDownClass(cls):
        cls._fake_dapr_server.stop()

    def setUp(self):
        server = self._fake_dapr_server
        server.actor_stream_plans.clear()
        server.actor_stream_initials.clear()
        server.actor_stream_replies.clear()
        server.actor_requests.clear()
        server.actor_state.clear()
        HostTestActor.reminders_fired.clear()
        HostTestActor.timers_fired.clear()
        HostTestActor.deactivated_ids.clear()
        self._saved_managers = dict(ActorRuntime._actor_managers)
        self._saved_config = ActorRuntime.get_actor_config()
        ActorRuntime._actor_managers.clear()
        ActorRuntime.set_actor_config(ActorRuntimeConfig())
        self.host = ActorGrpcHost(address=f'localhost:{GRPC_PORT}')

    async def asyncTearDown(self):
        await self.host.stop()
        ActorRuntime._actor_managers.clear()
        ActorRuntime._actor_managers.update(self._saved_managers)
        ActorRuntime.set_actor_config(self._saved_config)

    async def _serve_callbacks(self, *rounds, end='hold'):
        """Registers HostTestActor and starts the host against one scripted
        connection that pushes the given callback rounds."""
        await self._serve_plans(_plan(*rounds, end=end))

    async def _serve_plans(self, *plans):
        """Registers HostTestActor and starts the host; the fake daprd serves
        one plan per stream connection (reconnects consume the next plan)."""
        self._fake_dapr_server.actor_stream_plans.extend(plans)
        await self.host.register_actor(HostTestActor)
        await self.host.start()

    async def _await_replies(self, count: int, timeout: float = 5.0):
        """Returns the host's replies once `count` reached the fake daprd."""
        replies = self._fake_dapr_server.actor_stream_replies
        await self._wait_until(lambda: len(replies) >= count, timeout)
        return list(replies)

    async def _wait_until(self, predicate, timeout: float = 5.0):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if predicate():
                return
            await asyncio.sleep(0.02)
        raise AssertionError('condition not met within timeout')

    async def test_registration_advertises_entities_and_config(self):
        await self._serve_callbacks()

        initials = self._fake_dapr_server.actor_stream_initials
        self.assertEqual(1, len(initials))
        self.assertEqual(['HostTestActor'], list(initials[0].entities))
        self.assertEqual(3600, initials[0].actor_idle_timeout.seconds)
        self.assertTrue(initials[0].drain_rebalanced_actors)

    async def test_invoke_round_trip(self):
        await self._serve_callbacks([_invoke_message('req-1', 'GetName')])

        replies = await self._await_replies(1)

        reply = replies[0]
        self.assertEqual('invoke_response', reply.WhichOneof('request_type'))
        self.assertEqual('req-1', reply.invoke_response.id)
        self.assertFalse(reply.invoke_response.error)
        self.assertEqual({'name': 'HostTestActor'}, json.loads(reply.invoke_response.data))
        self.assertEqual('application/json', reply.invoke_response.metadata['content-type'])

    async def test_concurrent_invocations_correlate_by_id(self):
        invokes = [
            _invoke_message(f'req-{index}', 'Echo', json.dumps(index).encode('utf-8'))
            for index in range(5)
        ]
        await self._serve_callbacks(invokes)

        replies = await self._await_replies(5)

        responses = {reply.invoke_response.id: reply.invoke_response for reply in replies}
        for index in range(5):
            self.assertEqual(index, json.loads(responses[f'req-{index}'].data))

    async def test_unknown_actor_type_fails_with_not_found(self):
        await self._serve_callbacks([_invoke_message('req-1', 'GetName', actor_type='Unknown')])

        replies = await self._await_replies(1)

        reply = replies[0]
        self.assertEqual('request_failed', reply.WhichOneof('request_type'))
        self.assertEqual('req-1', reply.request_failed.id)
        self.assertEqual(StatusCode.NOT_FOUND.value[0], reply.request_failed.code)

    async def test_unknown_method_fails_with_not_found(self):
        await self._serve_callbacks([_invoke_message('req-1', 'NoSuchMethod')])

        replies = await self._await_replies(1)

        reply = replies[0]
        self.assertEqual('request_failed', reply.WhichOneof('request_type'))
        self.assertEqual(StatusCode.NOT_FOUND.value[0], reply.request_failed.code)

    async def test_handler_exception_returns_error_payload(self):
        await self._serve_callbacks([_invoke_message('req-1', 'Fail')])

        replies = await self._await_replies(1)

        reply = replies[0]
        self.assertEqual('invoke_response', reply.WhichOneof('request_type'))
        self.assertTrue(reply.invoke_response.error)
        payload = json.loads(reply.invoke_response.data)
        self.assertEqual('UNKNOWN', payload['errorCode'])
        self.assertIn('handler exploded', payload['message'])

    async def test_handler_value_error_returns_error_payload(self):
        """User-code ValueError is an application error, not an unknown-method
        NOT_FOUND, so the caller receives the error payload."""
        await self._serve_callbacks([_invoke_message('req-1', 'FailWithValueError')])

        replies = await self._await_replies(1)

        reply = replies[0]
        self.assertEqual('invoke_response', reply.WhichOneof('request_type'))
        self.assertTrue(reply.invoke_response.error)
        payload = json.loads(reply.invoke_response.data)
        self.assertIn('bad user input', payload['message'])

    async def test_reentrancy_id_reaches_actor_context(self):
        invoke = _invoke_message('req-1', 'WhoAmI', metadata={'Dapr-Reentrancy-Id': 'rid-42'})
        await self._serve_callbacks([invoke])

        replies = await self._await_replies(1)

        self.assertEqual('rid-42', json.loads(replies[0].invoke_response.data))

    async def test_reminder_round_trip(self):
        await self._serve_callbacks(
            [_reminder_message('req-1', 'demo_reminder', b'reminder_state')]
        )

        replies = await self._await_replies(1)

        reply = replies[0]
        self.assertEqual('reminder_response', reply.WhichOneof('request_type'))
        self.assertEqual('req-1', reply.reminder_response.id)
        self.assertFalse(reply.reminder_response.cancel)
        self.assertEqual([('demo_reminder', b'reminder_state')], HostTestActor.reminders_fired)

    async def test_timer_round_trip(self):
        timer = _timer_message('req-1', 'demo_timer', 'timer_callback', b'{"setting":1}')
        await self._serve_callbacks([timer])

        replies = await self._await_replies(1)

        reply = replies[0]
        self.assertEqual('timer_response', reply.WhichOneof('request_type'))
        self.assertEqual('req-1', reply.timer_response.id)
        self.assertEqual([{'setting': 1}], HostTestActor.timers_fired)

    async def test_deactivate_round_trip(self):
        # First round activates the actor instance, second round deactivates it.
        await self._serve_callbacks(
            [_invoke_message('req-1', 'GetName')],
            [_deactivate_message('req-2')],
        )

        replies = await self._await_replies(2)

        reply = replies[1]
        self.assertEqual('deactivate_response', reply.WhichOneof('request_type'))
        self.assertEqual('req-2', reply.deactivate_response.id)
        self.assertEqual(['a1'], HostTestActor.deactivated_ids)

    async def test_deactivate_unknown_instance_fails(self):
        await self._serve_callbacks([_deactivate_message('req-1', actor_id='never-activated')])

        replies = await self._await_replies(1)

        self.assertEqual('request_failed', replies[0].WhichOneof('request_type'))

    async def test_outbound_state_goes_over_grpc(self):
        """The actor's state operations go through the gRPC actor client the
        host wired in, not the HTTP one."""
        await self._serve_callbacks([_invoke_message('req-1', 'SaveData', b'{"color":"blue"}')])

        replies = await self._await_replies(1)

        self.assertFalse(replies[0].invoke_response.error)
        rpc_names = [name for name, _ in self._fake_dapr_server.actor_requests]
        self.assertIn('ExecuteActorStateTransaction', rpc_names)
        stored = self._fake_dapr_server.actor_state[('HostTestActor', 'a1', 'mydata')]
        self.assertEqual({'color': 'blue'}, json.loads(stored))

    async def test_reconnects_and_reregisters_after_disconnect(self):
        with mock.patch('dapr.actor.runtime.grpc_host._RECONNECT_DELAY_SECONDS', 0.05):
            await self._serve_plans(
                _plan([_invoke_message('req-1', 'GetName')], end='abort'),
                _plan([_invoke_message('req-2', 'GetName')]),
            )

            await self._wait_until(
                lambda: len(self._fake_dapr_server.actor_stream_initials) >= 2, timeout=10.0
            )
            replies = await self._await_replies(2, timeout=10.0)

        reply_ids = {reply.invoke_response.id for reply in replies}
        self.assertEqual({'req-1', 'req-2'}, reply_ids)

    async def test_start_raises_on_non_transient_rejection(self):
        self._fake_dapr_server.actor_stream_plans.append(
            _plan(reject=StatusCode.FAILED_PRECONDITION)
        )
        await self.host.register_actor(HostTestActor)

        with self.assertRaises(AioRpcError) as raised:
            await self.host.start()
        self.assertEqual(StatusCode.FAILED_PRECONDITION, raised.exception.code())
        # A failed start() must leave no channel or run task behind.
        self.assertIsNone(self.host._run_task)
        self.assertIsNone(self.host._channel)

    async def test_start_without_registered_actors_raises(self):
        with self.assertRaises(RuntimeError):
            await self.host.start()

    async def test_stop_before_start_is_a_noop(self):
        await self.host.stop()

    async def test_unknown_stream_message_is_ignored(self):
        from dapr.actor.runtime.grpc_host import _StreamSession

        session = mock.Mock(spec=_StreamSession)
        empty_message = api_v1.SubscribeActorEventsResponseAlpha1()

        with self.assertLogs('dapr.actor.runtime.grpc_host', level='WARNING') as logs:
            await self.host._dispatch(session, empty_message)

        session.send.assert_not_called()
        self.assertIn('Ignoring unexpected actor stream message', logs.output[0])

    async def test_context_manager(self):
        self._fake_dapr_server.actor_stream_plans.append(_plan())
        await self.host.register_actor(HostTestActor)

        async with self.host as host:
            self.assertTrue(host._registered.is_set())


if __name__ == '__main__':
    unittest.main()
