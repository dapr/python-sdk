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
from dapr.clients.grpc._response import (
    CONFIG_OUTAGE_WARNING_EVERY_N_FAILURES,
    ConfigurationResponse,
)
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

    async def test_catch_up_read_leaves_out_subscribe_only_metadata(self):
        server = self._fake_dapr_server
        server.config_values = {'k': 'changed-while-down'}
        server.config_stream_plans.extend(
            [
                {'id': 'first', 'end': 'abort'},
                {'id': 'second', 'end': 'hold'},
            ]
        )
        metadata = {'pgNotifyChannel': 'config', 'label': 'x'}

        await self.client.subscribe_configuration(
            store_name=STORE, keys=['k'], handler=self.handler, config_metadata=metadata
        )

        self.assertTrue(await wait_until(lambda: len(self.updates) == 1), self.updates)
        self.assertEqual(len(server.config_get_requests), 1)
        self.assertEqual(dict(server.config_get_requests[0].metadata), {'label': 'x'})
        for request in server.config_subscribe_requests:
            self.assertEqual(dict(request.metadata), metadata)

    async def test_long_outage_warns_again_every_n_failures(self):
        failing_attempts = 2 * CONFIG_OUTAGE_WARNING_EVERY_N_FAILURES + 1
        server = self._fake_dapr_server
        server.config_stream_plans.append({'id': 'first', 'end': 'abort'})
        server.config_stream_plans.extend(
            [{'reject': grpc.StatusCode.INVALID_ARGUMENT}] * (failing_attempts - 1)
        )
        server.config_stream_plans.append({'id': 'second', 'updates': [{'k': 'v2'}], 'end': 'hold'})

        with self.assertLogs('dapr.aio.clients.grpc._response', level='DEBUG') as logs:
            await self.subscribe()
            self.assertTrue(await wait_until(lambda: len(self.updates) == 1), self.updates)

        failures = [r for r in logs.records if 'failed, reconnecting' in r.getMessage()]
        self.assertEqual(len(failures), failing_attempts, logs.output)
        warnings = [r.getMessage() for r in failures if r.levelname == 'WARNING']
        self.assertEqual(len(warnings), 3, warnings)
        self.assertIn(
            f'still failing after {CONFIG_OUTAGE_WARNING_EVERY_N_FAILURES} attempts', warnings[1]
        )
        self.assertIn(
            f'still failing after {2 * CONFIG_OUTAGE_WARNING_EVERY_N_FAILURES} attempts',
            warnings[2],
        )

    async def test_no_configuration_stores_on_first_subscribe_returns_none_quickly(self):
        server = self._fake_dapr_server
        server.config_stream_plans.extend(
            [{'reject': grpc.StatusCode.FAILED_PRECONDITION}, {'id': 'unused', 'end': 'hold'}]
        )
        started = time.monotonic()

        self.assertIsNone(await self.subscribe())

        self.assertLess(time.monotonic() - started, 2.0)
        self.assertEqual(len(server.config_subscribe_requests), 1)
        self.assertEqual(self.client._config_watchers, {})

    async def test_unsubscribe_before_the_reconnect_stream_sent_its_id_stops_locally(self):
        server = self._fake_dapr_server
        id_gate = threading.Event()
        self.addCleanup(id_gate.set)
        server.config_stream_plans.extend(
            [
                {'id': 'first', 'end': 'abort'},
                {'id': 'second', 'end': 'hold', 'wait_before_id': id_gate},
            ]
        )
        subscription_id = await self.subscribe()
        watcher = self.watcher(subscription_id)
        self.assertTrue(
            await wait_until(
                lambda: len(server.config_subscribe_requests) == 2 and watcher._call is not None
            )
        )
        self.assertIsNone(watcher.live_stream_id())

        self.assertTrue(await self.client.unsubscribe_configuration(STORE, subscription_id))

        self.assertEqual(server.config_unsubscribe_requests, [])
        task = watcher._task
        assert task is not None
        self.assertTrue(task.done())
        self.assertNotIn((STORE, subscription_id), self.client._config_watchers)

    async def test_watcher_that_exited_before_registration_is_not_tracked(self):
        async def watch_and_exit(watcher: AsyncConfigurationWatcher, *args, **kwargs) -> str:
            watcher.store_name = STORE
            watcher.subscription_id = 'gone'
            watcher._exited = True
            return 'gone'

        with patch.object(AsyncConfigurationWatcher, 'watch_configuration', watch_and_exit):
            self.assertEqual(await self.subscribe(), 'gone')

        self.assertEqual(self.client._config_watchers, {})

    async def test_blocking_sync_handler_does_not_stall_the_event_loop(self):
        self._fake_dapr_server.config_stream_plans.append(
            {'id': 'first', 'updates': [{'k': 'v1'}, {'k': 'v2'}], 'end': 'hold'}
        )
        handler_started = threading.Event()
        handler_finished = threading.Event()
        release = threading.Event()
        self.addCleanup(release.set)
        received: List[str] = []

        def blocking_handler(subscription_id: str, response: ConfigurationResponse) -> None:
            handler_started.set()
            release.wait(2.0)
            received.append(response.items['k'].value)
            handler_finished.set()

        ticks = 0

        async def ticker() -> None:
            nonlocal ticks
            while True:
                ticks += 1
                await asyncio.sleep(0.01)

        ticker_task = asyncio.create_task(ticker())
        try:
            await self.client.subscribe_configuration(
                store_name=STORE, keys=['k'], handler=blocking_handler
            )
            self.assertTrue(await wait_until(handler_started.is_set))
            ticks_before = ticks
            await asyncio.sleep(0.2)
            ticks_while_blocked = ticks - ticks_before
            handler_was_blocked = not handler_finished.is_set()
        finally:
            release.set()
            ticker_task.cancel()

        self.assertTrue(handler_was_blocked)
        self.assertGreater(ticks_while_blocked, 0)
        # Calls stay sequential and in order.
        self.assertTrue(await wait_until(lambda: len(received) == 2), received)
        self.assertEqual(received, ['v1', 'v2'])

    async def test_each_outage_starts_with_a_warning(self):
        # A stream that delivered its id ends the outage, whether it then fails or closes
        # cleanly, so the next failure is the first of a new outage.
        self._fake_dapr_server.config_stream_plans.extend(
            [
                {'id': 'first', 'end': 'abort'},
                {'reject': grpc.StatusCode.UNAVAILABLE},
                {'id': 'second', 'end': 'abort'},
                {'reject': grpc.StatusCode.UNAVAILABLE},
                {'id': 'third', 'end': 'eof'},
                {'reject': grpc.StatusCode.UNAVAILABLE},
                {'id': 'fourth', 'updates': [{'k': 'v4'}], 'end': 'hold'},
            ]
        )

        with self.assertLogs('dapr.aio.clients.grpc._response', level='DEBUG') as logs:
            await self.subscribe()
            self.assertTrue(await wait_until(lambda: len(self.updates) == 1), self.updates)

        failures = [r for r in logs.records if 'failed, reconnecting' in r.getMessage()]
        self.assertEqual(
            [r.levelname for r in failures],
            ['WARNING', 'DEBUG', 'WARNING', 'DEBUG', 'WARNING'],
            logs.output,
        )
        self.assertFalse(
            any('still failing' in r.getMessage() for r in failures if r.levelname == 'WARNING')
        )


if __name__ == '__main__':
    unittest.main()
