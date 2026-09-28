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

import threading
import time
import unittest
from typing import Callable, List, Tuple
from unittest.mock import patch

import grpc

from dapr.clients.grpc._response import (
    CONFIG_RECONNECT_INITIAL_BACKOFF_SECONDS,
    CONFIG_RECONNECT_MAX_BACKOFF_SECONDS,
    ConfigurationResponse,
    ConfigurationWatcher,
    config_reconnect_delay,
    is_retryable_config_error,
)
from dapr.clients.grpc.client import DaprGrpcClient
from dapr.conf import settings

from .fake_dapr_server import FakeDaprSidecar

STORE = 'configstore'
WAIT_TIMEOUT_SECONDS = 5.0


def wait_until(condition: Callable[[], bool], timeout: float = WAIT_TIMEOUT_SECONDS) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if condition():
            return True
        time.sleep(0.01)
    return condition()


class _FakeRpcError(grpc.RpcError):
    def __init__(self, code: grpc.StatusCode):
        self._code = code

    def code(self) -> grpc.StatusCode:
        return self._code


class ConfigurationRetryHelpersTests(unittest.TestCase):
    def test_delay_doubles_and_is_capped(self):
        for attempt, base in [(0, 0.5), (1, 1.0), (2, 2.0), (3, 4.0), (4, 8.0), (10, 8.0)]:
            delay = config_reconnect_delay(attempt)
            self.assertGreaterEqual(delay, base)
            self.assertLessEqual(delay, base * 1.2)
        self.assertEqual(CONFIG_RECONNECT_INITIAL_BACKOFF_SECONDS, 0.5)
        self.assertEqual(CONFIG_RECONNECT_MAX_BACKOFF_SECONDS, 8.0)

    def test_retryable_classification(self):
        for code in (
            grpc.StatusCode.UNAVAILABLE,
            grpc.StatusCode.UNKNOWN,
            grpc.StatusCode.INTERNAL,
            grpc.StatusCode.CANCELLED,
            grpc.StatusCode.DEADLINE_EXCEEDED,
        ):
            self.assertTrue(is_retryable_config_error(_FakeRpcError(code)), code)
        for code in (
            grpc.StatusCode.INVALID_ARGUMENT,
            grpc.StatusCode.NOT_FOUND,
            grpc.StatusCode.PERMISSION_DENIED,
            grpc.StatusCode.UNAUTHENTICATED,
            grpc.StatusCode.UNIMPLEMENTED,
        ):
            self.assertFalse(is_retryable_config_error(_FakeRpcError(code)), code)
        self.assertFalse(is_retryable_config_error(ValueError('closed channel')))


class ConfigurationWatcherReconnectTests(unittest.TestCase):
    grpc_port = 50021
    http_port = 3521

    @classmethod
    def setUpClass(cls):
        cls._fake_dapr_server = FakeDaprSidecar(grpc_port=cls.grpc_port, http_port=cls.http_port)
        cls._fake_dapr_server.start()
        settings.DAPR_HTTP_PORT = cls.http_port
        settings.DAPR_HTTP_ENDPOINT = 'http://127.0.0.1:{}'.format(cls.http_port)

    @classmethod
    def tearDownClass(cls):
        cls._fake_dapr_server.stop()

    def setUp(self):
        server = self._fake_dapr_server
        server.config_stream_plans.clear()
        server.config_subscribe_requests.clear()
        server.config_unsubscribe_requests.clear()
        self.delays: List[float] = []
        self.updates: List[Tuple[str, str]] = []

        def record_wait(watcher: ConfigurationWatcher, delay: float) -> bool:
            self.delays.append(delay)
            return watcher._stop_event.is_set()

        patcher = patch.object(ConfigurationWatcher, '_wait_before_retry', record_wait)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.client = DaprGrpcClient(f'localhost:{self.grpc_port}')
        self.addCleanup(self.client.close)

    def handler(self, subscription_id: str, response: ConfigurationResponse) -> None:
        self.updates.append((subscription_id, response.items['k'].value))

    def subscribe(self) -> str:
        return self.client.subscribe_configuration(
            store_name=STORE, keys=['k'], handler=self.handler
        )

    def watcher(self, subscription_id: str) -> ConfigurationWatcher:
        return self.client._config_watchers[(STORE, subscription_id)]

    def test_reconnects_after_stream_error_and_keeps_delivering(self):
        self._fake_dapr_server.config_stream_plans.extend(
            [
                {'id': 'first', 'updates': [{'k': 'v1'}], 'end': 'abort'},
                {'id': 'second', 'updates': [{'k': 'v2'}], 'end': 'hold'},
            ]
        )

        subscription_id = self.subscribe()

        self.assertEqual(subscription_id, 'first')
        self.assertTrue(wait_until(lambda: len(self.updates) == 2), self.updates)
        self.assertEqual(self.updates, [('first', 'v1'), ('first', 'v2')])
        requests = self._fake_dapr_server.config_subscribe_requests
        self.assertEqual(len(requests), 2)
        self.assertEqual(requests[0], requests[1])
        self.assertEqual(self.watcher('first').id, 'second')

    def test_reconnects_after_clean_stream_end(self):
        self._fake_dapr_server.config_stream_plans.extend(
            [
                {'id': 'first', 'updates': [{'k': 'v1'}], 'end': 'eof'},
                {'id': 'second', 'updates': [{'k': 'v2'}], 'end': 'hold'},
            ]
        )

        self.subscribe()

        self.assertTrue(wait_until(lambda: len(self.updates) == 2), self.updates)
        self.assertEqual(self.updates, [('first', 'v1'), ('first', 'v2')])

    def test_unsubscribe_after_reconnect_uses_new_id_and_stops(self):
        server = self._fake_dapr_server
        server.config_stream_plans.extend(
            [
                {'id': 'first', 'end': 'abort'},
                {'id': 'second', 'updates': [{'k': 'v2'}], 'end': 'hold'},
            ]
        )
        subscription_id = self.subscribe()
        self.assertTrue(wait_until(lambda: len(self.updates) == 1), self.updates)
        watcher = self.watcher(subscription_id)
        thread = watcher._thread
        assert thread is not None

        self.assertTrue(self.client.unsubscribe_configuration(STORE, subscription_id))

        self.assertEqual([r.id for r in server.config_unsubscribe_requests], ['second'])
        self.assertEqual([r.store_name for r in server.config_unsubscribe_requests], [STORE])
        self.assertFalse(thread.is_alive())
        self.assertTrue(watcher.stopped)
        self.assertNotIn((STORE, subscription_id), self.client._config_watchers)
        time.sleep(0.2)
        self.assertEqual(len(server.config_subscribe_requests), 2)

    def test_unsubscribe_unknown_id_is_sent_as_is(self):
        self.assertTrue(self.client.unsubscribe_configuration(STORE, 'not-tracked'))
        self.assertEqual(
            [r.id for r in self._fake_dapr_server.config_unsubscribe_requests], ['not-tracked']
        )

    def test_non_retryable_error_stops_without_reconnecting(self):
        server = self._fake_dapr_server
        server.config_stream_plans.extend(
            [
                {
                    'id': 'first',
                    'updates': [{'k': 'v1'}],
                    'end': 'abort',
                    'code': grpc.StatusCode.PERMISSION_DENIED,
                },
                {'id': 'second', 'updates': [{'k': 'v2'}], 'end': 'hold'},
            ]
        )
        subscription_id = self.subscribe()
        thread = self.watcher(subscription_id)._thread
        assert thread is not None

        thread.join(timeout=WAIT_TIMEOUT_SECONDS)

        self.assertFalse(thread.is_alive())
        self.assertEqual(self.updates, [('first', 'v1')])
        self.assertEqual(len(server.config_subscribe_requests), 1)
        self.assertEqual(self.delays, [])

    def test_non_retryable_error_on_first_connection_returns_none_quickly(self):
        server = self._fake_dapr_server
        server.config_stream_plans.extend(
            [{'reject': grpc.StatusCode.INVALID_ARGUMENT}, {'id': 'unused', 'end': 'hold'}]
        )
        threads_before = threading.active_count()

        started = time.monotonic()
        subscription_id = self.subscribe()

        self.assertIsNone(subscription_id)
        self.assertLess(time.monotonic() - started, 2.0)
        self.assertEqual(len(server.config_subscribe_requests), 1)
        self.assertEqual(self.client._config_watchers, {})
        self.assertTrue(wait_until(lambda: threading.active_count() <= threads_before))

    def test_backoff_grows_on_consecutive_failures_and_resets_after_success(self):
        server = self._fake_dapr_server
        server.config_stream_plans.extend(
            [
                {'reject': grpc.StatusCode.UNAVAILABLE},
                {'reject': grpc.StatusCode.UNAVAILABLE},
                {'reject': grpc.StatusCode.UNAVAILABLE},
                {'id': 'first', 'end': 'abort'},
                {'id': 'second', 'updates': [{'k': 'v1'}], 'end': 'hold'},
            ]
        )

        subscription_id = self.subscribe()

        self.assertEqual(subscription_id, 'first')
        self.assertTrue(wait_until(lambda: len(self.updates) == 1), self.updates)
        self.assertEqual(len(self.delays), 4, self.delays)
        for delay, base in zip(self.delays, [0.5, 1.0, 2.0, 0.5]):
            self.assertGreaterEqual(delay, base)
            self.assertLessEqual(delay, base * 1.2)

    def test_handler_exception_does_not_stop_subscription(self):
        self._fake_dapr_server.config_stream_plans.append(
            {'id': 'first', 'updates': [{'k': 'boom'}, {'k': 'v2'}], 'end': 'hold'}
        )

        def handler(subscription_id: str, response: ConfigurationResponse) -> None:
            value = response.items['k'].value
            if value == 'boom':
                raise RuntimeError('handler failure')
            self.updates.append((subscription_id, value))

        self.client.subscribe_configuration(store_name=STORE, keys=['k'], handler=handler)

        self.assertTrue(wait_until(lambda: len(self.updates) == 1), self.updates)
        self.assertEqual(self.updates, [('first', 'v2')])
        self.assertEqual(len(self._fake_dapr_server.config_subscribe_requests), 1)

    def test_close_stops_watchers(self):
        self._fake_dapr_server.config_stream_plans.append({'id': 'first', 'end': 'hold'})
        subscription_id = self.subscribe()
        watcher = self.watcher(subscription_id)
        thread = watcher._thread
        assert thread is not None

        self.client.close()

        self.assertFalse(thread.is_alive())
        self.assertTrue(watcher.stopped)
        self.assertEqual(self.client._config_watchers, {})


if __name__ == '__main__':
    unittest.main()
