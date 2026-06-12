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
"""

import base64
import json
import unittest
from datetime import timedelta

from dapr.actor.runtime._reminder_data import ActorReminderData
from dapr.actor.runtime._timer_data import ActorTimerData
from dapr.actor.runtime.failure_policy import ActorReminderFailurePolicy
from dapr.actor.runtime.reentrancy_context import reentrancy_ctx
from dapr.clients.grpc.dapr_actor_grpc_client import DaprActorGrpcClient
from dapr.serializers import DefaultJSONSerializer

from .fake_dapr_server import FakeDaprSidecar


class DaprActorGrpcClientTests(unittest.IsolatedAsyncioTestCase):
    grpc_port = 50001
    http_port = 3500

    @classmethod
    def setUpClass(cls):
        cls._fake_dapr_server = FakeDaprSidecar(grpc_port=cls.grpc_port, http_port=cls.http_port)
        cls._fake_dapr_server.start()

    @classmethod
    def tearDownClass(cls):
        cls._fake_dapr_server.stop()

    def setUp(self):
        self._fake_dapr_server.actor_requests.clear()
        self._fake_dapr_server.actor_state.clear()
        self._serializer = DefaultJSONSerializer()
        self.client = DaprActorGrpcClient(address=f'localhost:{self.grpc_port}')

    async def asyncTearDown(self):
        await self.client.close()

    def _last_request(self, expected_rpc: str):
        rpc_name, request = self._fake_dapr_server.actor_requests[-1]
        self.assertEqual(expected_rpc, rpc_name)
        return request

    async def test_invoke_method(self):
        response = await self.client.invoke_method('DemoActor', 'a1', 'DoSomething', b'"hi"')

        self.assertEqual(b'"hi"', response)
        request = self._last_request('InvokeActor')
        self.assertEqual('DemoActor', request.actor_type)
        self.assertEqual('a1', request.actor_id)
        self.assertEqual('DoSomething', request.method)
        self.assertEqual({}, dict(request.metadata))

    async def test_invoke_method_propagates_reentrancy_id(self):
        token = reentrancy_ctx.set('rid-123')
        try:
            await self.client.invoke_method('DemoActor', 'a1', 'DoSomething', b'')
        finally:
            reentrancy_ctx.reset(token)

        request = self._last_request('InvokeActor')
        self.assertEqual({'Dapr-Reentrancy-Id': 'rid-123'}, dict(request.metadata))

    async def test_get_state(self):
        self._fake_dapr_server.actor_state[('DemoActor', 'a1', 'mydata')] = b'{"x":1}'

        value = await self.client.get_state('DemoActor', 'a1', 'mydata')
        missing = await self.client.get_state('DemoActor', 'a1', 'missing')

        self.assertEqual(b'{"x":1}', value)
        self.assertEqual(b'', missing)

    async def test_save_state_transactionally(self):
        operations = [
            {
                'operation': 'upsert',
                'request': {'key': 'key1', 'value': {'x': 1}, 'metadata': {'ttlInSeconds': '60'}},
            },
            {'operation': 'delete', 'request': {'key': 'key2'}},
        ]
        body = json.dumps(operations).encode('utf-8')

        await self.client.save_state_transactionally('DemoActor', 'a1', body)

        request = self._last_request('ExecuteActorStateTransaction')
        self.assertEqual(2, len(request.operations))

        upsert = request.operations[0]
        self.assertEqual('upsert', upsert.operationType)
        self.assertEqual('key1', upsert.key)
        # daprd persists Any.value verbatim, so the bytes must match the
        # runtime serializer's compact output, not spaced json.dumps defaults.
        self.assertEqual(b'{"x":1}', upsert.value.value)
        self.assertEqual({'ttlInSeconds': '60'}, dict(upsert.metadata))

        delete = request.operations[1]
        self.assertEqual('delete', delete.operationType)
        self.assertEqual('key2', delete.key)
        self.assertEqual(
            b'{"x":1}', self._fake_dapr_server.actor_state[('DemoActor', 'a1', 'key1')]
        )

    async def test_register_reminder(self):
        state = b'reminder_state'
        reminder = ActorReminderData(
            'demo_reminder',
            state,
            timedelta(seconds=5),
            timedelta(seconds=10),
            timedelta(minutes=1),
            failure_policy=ActorReminderFailurePolicy.constant_policy(
                interval=timedelta(seconds=2), max_retries=3
            ),
        )
        body = self._serializer.serialize(reminder.as_dict())

        await self.client.register_reminder('DemoActor', 'a1', 'demo_reminder', body)

        request = self._last_request('RegisterActorReminder')
        self.assertEqual('DemoActor', request.actor_type)
        self.assertEqual('a1', request.actor_id)
        self.assertEqual('demo_reminder', request.name)
        self.assertEqual('0h0m5s0ms0μs', request.due_time)
        self.assertEqual('0h0m10s0ms0μs', request.period)
        self.assertEqual('0h1m0s0ms0μs', request.ttl)
        self.assertEqual(state, request.data)
        self.assertTrue(request.HasField('failure_policy'))
        self.assertEqual(2, request.failure_policy.constant.interval.seconds)
        self.assertEqual(3, request.failure_policy.constant.max_retries)

    async def test_register_reminder_with_drop_policy(self):
        reminder = ActorReminderData(
            'demo_reminder',
            b'',
            timedelta(seconds=5),
            timedelta(seconds=10),
            failure_policy=ActorReminderFailurePolicy.drop_policy(),
        )
        body = self._serializer.serialize(reminder.as_dict())

        await self.client.register_reminder('DemoActor', 'a1', 'demo_reminder', body)

        request = self._last_request('RegisterActorReminder')
        self.assertEqual(b'', request.data)
        self.assertTrue(request.failure_policy.HasField('drop'))

    async def test_register_reminder_state_round_trip(self):
        """The registered bytes must equal the raw state so daprd's base64
        wrapping reproduces the JSON value the HTTP endpoint stores."""
        state = b'{"nested": "value"}'
        reminder = ActorReminderData('r', state, timedelta(seconds=1), timedelta(seconds=1))
        body = self._serializer.serialize(reminder.as_dict())

        await self.client.register_reminder('DemoActor', 'a1', 'r', body)

        request = self._last_request('RegisterActorReminder')
        self.assertEqual(state, request.data)
        body_dict = json.loads(body)
        self.assertEqual(base64.b64decode(body_dict['data']), request.data)

    async def test_register_timer(self):
        async def timer_callback(state):
            pass

        timer = ActorTimerData(
            'demo_timer',
            timer_callback,
            {'setting': 1},
            timedelta(seconds=5),
            timedelta(seconds=10),
            timedelta(minutes=2),
        )
        body = self._serializer.serialize(timer.as_dict())

        await self.client.register_timer('DemoActor', 'a1', 'demo_timer', body)

        request = self._last_request('RegisterActorTimer')
        self.assertEqual('demo_timer', request.name)
        self.assertEqual('timer_callback', request.callback)
        self.assertEqual('0h0m5s0ms0μs', request.due_time)
        self.assertEqual('0h0m10s0ms0μs', request.period)
        self.assertEqual('0h2m0s0ms0μs', request.ttl)
        # daprd base64-wraps these bytes and the host recovers them verbatim,
        # so they must match the runtime serializer's compact output.
        self.assertEqual(b'{"setting":1}', request.data)

    async def test_unregister_reminder_and_timer(self):
        await self.client.unregister_reminder('DemoActor', 'a1', 'demo_reminder')
        await self.client.unregister_timer('DemoActor', 'a1', 'demo_timer')

        rpc_names = [name for name, _ in self._fake_dapr_server.actor_requests]
        self.assertEqual(['UnregisterActorReminder', 'UnregisterActorTimer'], rpc_names)


if __name__ == '__main__':
    unittest.main()
