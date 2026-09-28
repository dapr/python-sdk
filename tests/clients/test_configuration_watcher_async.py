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

import asyncio
import threading
import time
import unittest
from typing import Callable, List, Tuple
from unittest.mock import patch

import grpc

from dapr.aio.clients.grpc._response import AsyncConfigurationWatcher
from dapr.aio.clients.grpc.client import DaprGrpcClientAsync
from dapr.clients.grpc._response import ConfigurationResponse
from dapr.conf import settings

from .fake_dapr_server import FakeDaprSidecar

STORE = 'configstore'
WAIT_TIMEOUT_SECONDS = 5.0


async def wait_until(condition: Callable[[], bool], timeout: float = WAIT_TIMEOUT_SECONDS) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if condition():
            return True
        await asyncio.sleep(0.01)
    return condition()


class AsyncConfigurationWatcherReconnectTests(unittest.IsolatedAsyncioTestCase):
    grpc_port = 50022
    http_port = 3522

    @classmethod
    def setUpClass(cls):
        cls._fake_dapr_server = FakeDaprSidecar(grpc_port=cls.grpc_port, http_port=cls.http_port)
        cls._fake_dapr_server.start()
        settings.DAPR_HTTP_PORT = cls.http_port
        settings.DAPR_HTTP_ENDPOINT = 'http://127.0.0.1:{}'.format(cls.http_port)

    @classmethod
    def tearDownClass(cls):
        cls._fake_dapr_server.stop()

    async def asyncSetUp(self):
        server = self._fake_dapr_server
        server.config_stream_plans.clear()
        server.config_subscribe_requests.clear()
        server.config_unsubscribe_requests.clear()
        server.config_get_requests.clear()
        # No current values unless a test sets them, so reconnects add no handler calls.
        server.config_values = {}
        server.config_get_error = None
        self.delays: List[float] = []
        self.updates: List[Tuple[str, str]] = []

        async def record_wait(watcher: AsyncConfigurationWatcher, delay: float) -> None:
            self.delays.append(delay)

        patcher = patch.object(AsyncConfigurationWatcher, '_wait_before_retry', record_wait)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.client = DaprGrpcClientAsync(f'localhost:{self.grpc_port}')
        self.addAsyncCleanup(self.client.close)

    def handler(self, subscription_id: str, response: ConfigurationResponse) -> None:
        self.updates.append((subscription_id, response.items['k'].value))

    async def subscribe(self) -> str:
        return await self.client.subscribe_configuration(
            store_name=STORE, keys=['k'], handler=self.handler
        )

    def watcher(self, subscription_id: str) -> AsyncConfigurationWatcher:
        return self.client._config_watchers[(STORE, subscription_id)]

    async def test_subscribe_returns_id_and_delivers_updates(self):
        self._fake_dapr_server.config_stream_plans.append(
            {'id': 'first', 'updates': [{'k': 'v1'}], 'end': 'hold'}
        )

        subscription_id = await self.subscribe()

        self.assertEqual(subscription_id, 'first')
        self.assertTrue(await wait_until(lambda: len(self.updates) == 1), self.updates)
        self.assertEqual(self.updates, [('first', 'v1')])

    async def test_reconnects_after_stream_error_and_keeps_delivering(self):
        self._fake_dapr_server.config_stream_plans.extend(
            [
                {'id': 'first', 'updates': [{'k': 'v1'}], 'end': 'abort'},
                {'id': 'second', 'updates': [{'k': 'v2'}], 'end': 'hold'},
            ]
        )

        await self.subscribe()

        self.assertTrue(await wait_until(lambda: len(self.updates) == 2), self.updates)
        self.assertEqual(self.updates, [('first', 'v1'), ('first', 'v2')])
        self.assertEqual(len(self._fake_dapr_server.config_subscribe_requests), 2)
        self.assertEqual(self.watcher('first').id, 'second')

    async def test_reconnects_after_clean_stream_end(self):
        self._fake_dapr_server.config_stream_plans.extend(
            [
                {'id': 'first', 'updates': [{'k': 'v1'}], 'end': 'eof'},
                {'id': 'second', 'updates': [{'k': 'v2'}], 'end': 'hold'},
            ]
        )

        await self.subscribe()

        self.assertTrue(await wait_until(lambda: len(self.updates) == 2), self.updates)

    async def test_unsubscribe_after_reconnect_uses_new_id_and_stops(self):
        server = self._fake_dapr_server
        server.config_stream_plans.extend(
            [
                {'id': 'first', 'end': 'abort'},
                {'id': 'second', 'updates': [{'k': 'v2'}], 'end': 'hold'},
            ]
        )
        subscription_id = await self.subscribe()
        self.assertTrue(await wait_until(lambda: len(self.updates) == 1), self.updates)
        watcher = self.watcher(subscription_id)
        task = watcher._task
        assert task is not None

        self.assertTrue(await self.client.unsubscribe_configuration(STORE, subscription_id))

        self.assertEqual([r.id for r in server.config_unsubscribe_requests], ['second'])
        self.assertTrue(task.done())
        self.assertNotIn((STORE, subscription_id), self.client._config_watchers)
        await asyncio.sleep(0.2)
        self.assertEqual(len(server.config_subscribe_requests), 2)

    async def test_non_retryable_error_stops_without_reconnecting(self):
        server = self._fake_dapr_server
        server.config_stream_plans.extend(
            [
                {
                    'id': 'first',
                    'updates': [{'k': 'v1'}],
                    'end': 'abort',
                    'code': grpc.StatusCode.UNIMPLEMENTED,
                },
                {'id': 'second', 'updates': [{'k': 'v2'}], 'end': 'hold'},
            ]
        )
        subscription_id = await self.subscribe()
        task = self.watcher(subscription_id)._task
        assert task is not None

        await asyncio.wait_for(asyncio.shield(task), timeout=WAIT_TIMEOUT_SECONDS)

        self.assertEqual(self.updates, [('first', 'v1')])
        self.assertEqual(len(server.config_subscribe_requests), 1)
        self.assertEqual(self.delays, [])

    async def test_non_retryable_error_on_first_connection_returns_none_quickly(self):
        self._fake_dapr_server.config_stream_plans.extend(
            [{'reject': grpc.StatusCode.UNAUTHENTICATED}, {'id': 'unused', 'end': 'hold'}]
        )

        started = time.monotonic()
        subscription_id = await self.subscribe()

        self.assertIsNone(subscription_id)
        self.assertLess(time.monotonic() - started, 2.0)
        self.assertEqual(len(self._fake_dapr_server.config_subscribe_requests), 1)
        self.assertEqual(self.client._config_watchers, {})

    @patch('dapr.clients.grpc._response.CONFIG_STABLE_STREAM_SECONDS', 0)
    async def test_backoff_grows_on_consecutive_failures_and_resets_after_success(self):
        self._fake_dapr_server.config_stream_plans.extend(
            [
                {'reject': grpc.StatusCode.UNAVAILABLE},
                {'reject': grpc.StatusCode.UNAVAILABLE},
                {'id': 'first', 'end': 'abort'},
                {'id': 'second', 'updates': [{'k': 'v1'}], 'end': 'hold'},
            ]
        )

        self.assertEqual(await self.subscribe(), 'first')

        self.assertTrue(await wait_until(lambda: len(self.updates) == 1), self.updates)
        self.assertEqual(len(self.delays), 3, self.delays)
        for delay, base in zip(self.delays, [0.5, 1.0, 0.5]):
            self.assertGreaterEqual(delay, base)
            self.assertLessEqual(delay, base * 1.2)

    async def test_close_stops_watchers(self):
        self._fake_dapr_server.config_stream_plans.append({'id': 'first', 'end': 'hold'})
        subscription_id = await self.subscribe()
        task = self.watcher(subscription_id)._task
        assert task is not None

        await self.client.close()

        self.assertTrue(task.done())
        self.assertEqual(self.client._config_watchers, {})

    async def test_backoff_keeps_growing_when_streams_close_right_after_the_id(self):
        self._fake_dapr_server.config_stream_plans.extend(
            [
                {'id': 'first', 'end': 'abort'},
                {'id': 'second', 'end': 'abort'},
                {'id': 'third', 'updates': [{'k': 'v1'}], 'end': 'hold'},
            ]
        )

        self.assertEqual(await self.subscribe(), 'first')

        self.assertTrue(await wait_until(lambda: len(self.updates) == 1), self.updates)
        self.assertEqual(len(self.delays), 2, self.delays)
        for delay, base in zip(self.delays, [0.5, 1.0]):
            self.assertGreaterEqual(delay, base)
            self.assertLessEqual(delay, base * 1.2)

    async def test_unsubscribe_unknown_id_is_sent_as_is(self):
        self.assertFalse(await self.client.unsubscribe_configuration(STORE, 'not-tracked'))
        self.assertEqual(
            [r.id for r in self._fake_dapr_server.config_unsubscribe_requests], ['not-tracked']
        )

    async def test_unsubscribe_while_reconnecting_stops_locally(self):
        server = self._fake_dapr_server
        server.config_stream_plans.extend(
            [
                {'id': 'first', 'end': 'abort'},
                {'id': 'second', 'updates': [{'k': 'v2'}], 'end': 'hold'},
            ]
        )
        waiting = asyncio.Event()

        async def wait_forever(watcher: AsyncConfigurationWatcher, delay: float) -> None:
            waiting.set()
            await asyncio.sleep(WAIT_TIMEOUT_SECONDS)

        with patch.object(AsyncConfigurationWatcher, '_wait_before_retry', wait_forever):
            subscription_id = await self.subscribe()
            watcher = self.watcher(subscription_id)
            await asyncio.wait_for(waiting.wait(), WAIT_TIMEOUT_SECONDS)
            self.assertIsNone(watcher.live_stream_id())

            self.assertTrue(await self.client.unsubscribe_configuration(STORE, subscription_id))

        self.assertEqual(server.config_unsubscribe_requests, [])
        task = watcher._task
        assert task is not None
        self.assertTrue(task.done())
        self.assertNotIn((STORE, subscription_id), self.client._config_watchers)
        self.assertEqual(len(server.config_subscribe_requests), 1)

    async def test_invalid_argument_after_the_subscription_was_established_is_retried(self):
        self._fake_dapr_server.config_stream_plans.extend(
            [
                {'id': 'first', 'updates': [{'k': 'v1'}], 'end': 'abort'},
                {'reject': grpc.StatusCode.INVALID_ARGUMENT},
                {'id': 'third', 'updates': [{'k': 'v3'}], 'end': 'hold'},
            ]
        )

        self.assertEqual(await self.subscribe(), 'first')

        self.assertTrue(await wait_until(lambda: len(self.updates) == 2), self.updates)
        self.assertEqual(self.updates, [('first', 'v1'), ('first', 'v3')])
        self.assertEqual(len(self._fake_dapr_server.config_subscribe_requests), 3)
        self.assertEqual(self.watcher('first').live_stream_id(), 'third')

    async def test_reconnect_delivers_current_values(self):
        server = self._fake_dapr_server
        server.config_values = {'k': 'changed-while-down'}
        server.config_stream_plans.extend(
            [
                {'id': 'first', 'updates': [{'k': 'v1'}], 'end': 'abort'},
                {'id': 'second', 'end': 'hold'},
            ]
        )

        await self.client.subscribe_configuration(
            store_name=STORE, keys=['k'], handler=self.handler, config_metadata={'m': '1'}
        )

        self.assertTrue(await wait_until(lambda: len(self.updates) == 2), self.updates)
        self.assertEqual(self.updates, [('first', 'v1'), ('first', 'changed-while-down')])
        self.assertEqual(len(server.config_get_requests), 1)
        get_request = server.config_get_requests[0]
        self.assertEqual(get_request.store_name, STORE)
        self.assertEqual(list(get_request.keys), ['k'])
        self.assertEqual(dict(get_request.metadata), {'m': '1'})

    async def test_first_subscribe_does_not_read_current_values(self):
        server = self._fake_dapr_server
        server.config_values = {'k': 'current'}
        server.config_stream_plans.append({'id': 'first', 'updates': [{'k': 'v1'}], 'end': 'hold'})

        await self.subscribe()

        self.assertTrue(await wait_until(lambda: len(self.updates) == 1), self.updates)
        await asyncio.sleep(0.2)
        self.assertEqual(self.updates, [('first', 'v1')])
        self.assertEqual(server.config_get_requests, [])

    async def test_failed_current_values_read_keeps_the_subscription(self):
        server = self._fake_dapr_server
        server.config_get_error = grpc.StatusCode.INTERNAL
        server.config_stream_plans.extend(
            [
                {'id': 'first', 'updates': [{'k': 'v1'}], 'end': 'abort'},
                {'id': 'second', 'updates': [{'k': 'v2'}], 'end': 'hold'},
            ]
        )

        with self.assertLogs('dapr.aio.clients.grpc._response', level='WARNING') as logs:
            await self.subscribe()
            self.assertTrue(await wait_until(lambda: len(self.updates) == 2), self.updates)

        self.assertEqual(self.updates, [('first', 'v1'), ('first', 'v2')])
        self.assertEqual(len(server.config_get_requests), 1)
        self.assertEqual(len(server.config_subscribe_requests), 2)
        self.assertTrue(
            any('Could not read the current configuration' in line for line in logs.output),
            logs.output,
        )

    async def test_watcher_that_gives_up_is_removed_from_the_client(self):
        release = threading.Event()
        self._fake_dapr_server.config_stream_plans.append(
            {
                'id': 'first',
                'end': 'abort',
                'code': grpc.StatusCode.PERMISSION_DENIED,
                'wait': release,
            }
        )
        subscription_id = await self.subscribe()
        self.assertIn((STORE, subscription_id), self.client._config_watchers)

        release.set()

        self.assertTrue(
            await wait_until(lambda: (STORE, subscription_id) not in self.client._config_watchers)
        )

    async def test_stop_requested_while_opening_a_stream_cancels_it(self):
        release = threading.Event()
        self._fake_dapr_server.config_stream_plans.extend(
            [
                {'id': 'first', 'end': 'abort', 'wait': release},
                {'id': 'second', 'end': 'hold'},
            ]
        )
        subscription_id = await self.subscribe()
        watcher = self.watcher(subscription_id)
        stub = self.client._stub
        real_subscribe = stub.SubscribeConfigurationAlpha1
        opened: List[grpc.aio.Call] = []

        def subscribe_and_stop(req):
            call = real_subscribe(req)
            opened.append(call)
            # stop() arrives while the watcher is opening the reconnect stream.
            watcher.request_stop()
            return call

        stub.SubscribeConfigurationAlpha1 = subscribe_and_stop
        release.set()

        self.assertTrue(await wait_until(lambda: watcher.exited))
        self.assertEqual(len(opened), 1)
        self.assertTrue(opened[0].cancelled())
        self.assertIsNone(watcher._call)

    async def test_reconnect_failures_are_logged_concisely_and_once_per_outage(self):
        self._fake_dapr_server.config_stream_plans.extend(
            [
                {'id': 'first', 'end': 'abort'},
                {'reject': grpc.StatusCode.UNAVAILABLE},
                {'reject': grpc.StatusCode.UNAVAILABLE},
                {'id': 'second', 'updates': [{'k': 'v2'}], 'end': 'hold'},
            ]
        )

        with self.assertLogs('dapr.aio.clients.grpc._response', level='DEBUG') as logs:
            await self.subscribe()
            self.assertTrue(await wait_until(lambda: len(self.updates) == 1), self.updates)

        failures = [r for r in logs.records if 'failed, reconnecting' in r.getMessage()]
        self.assertEqual(
            [r.levelname for r in failures], ['WARNING', 'DEBUG', 'DEBUG'], logs.output
        )
        for record in failures:
            message = record.getMessage()
            self.assertNotIn('\n', message)
            self.assertIn(': UNAVAILABLE: ', message)
        self.assertTrue(
            any(
                r.levelname == 'INFO' and 'reconnected with new id second' in r.getMessage()
                for r in logs.records
            ),
            logs.output,
        )

    async def test_async_handler_is_awaited(self):
        self._fake_dapr_server.config_stream_plans.append(
            {'id': 'first', 'updates': [{'k': 'v1'}], 'end': 'hold'}
        )
        received: List[Tuple[str, str]] = []

        async def async_handler(subscription_id: str, response: ConfigurationResponse) -> None:
            await asyncio.sleep(0)
            received.append((subscription_id, response.items['k'].value))

        subscription_id = await self.client.subscribe_configuration(
            store_name=STORE, keys=['k'], handler=async_handler
        )

        self.assertEqual(subscription_id, 'first')
        self.assertTrue(await wait_until(lambda: len(received) == 1), received)
        self.assertEqual(received, [('first', 'v1')])


if __name__ == '__main__':
    unittest.main()
