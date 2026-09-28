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
from typing import Callable, Iterator, List, Tuple
from unittest.mock import patch

import grpc

from dapr.clients.grpc._response import (
    CONFIG_RECONNECT_INITIAL_BACKOFF_SECONDS,
    CONFIG_RECONNECT_MAX_BACKOFF_SECONDS,
    ConfigurationResponse,
    ConfigurationWatcher,
    config_reconnect_delay,
    describe_config_error,
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
    def __init__(self, code: grpc.StatusCode, details: str = ''):
        self._code = code
        self._details = details

    def code(self) -> grpc.StatusCode:
        return self._code

    def details(self) -> str:
        return self._details


class _CancelRecordingCall:
    """Wraps a stream call and records cancel(). The call may be a plain generator when
    OpenTelemetry grpc instrumentation is active, so it is not asked whether it was cancelled."""

    def __init__(self, call: Iterator):
        self._call = call
        self.cancel_called = False

    def cancel(self) -> None:
        self.cancel_called = True
        cancel = getattr(self._call, 'cancel', None)
        if callable(cancel):
            cancel()

    def __iter__(self) -> Iterator:
        return iter(self._call)


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

    def test_retryable_classification_after_the_subscription_was_established(self):
        # daprd reports a failed store Subscribe (e.g. backend unreachable) and a store that
        # is not loaded as INVALID_ARGUMENT; once a subscription existed those are retried.
        for code in (
            grpc.StatusCode.INVALID_ARGUMENT,
            grpc.StatusCode.NOT_FOUND,
            grpc.StatusCode.FAILED_PRECONDITION,
            grpc.StatusCode.UNAVAILABLE,
            grpc.StatusCode.INTERNAL,
        ):
            self.assertTrue(is_retryable_config_error(_FakeRpcError(code), established=True), code)
        for code in (
            grpc.StatusCode.UNIMPLEMENTED,
            grpc.StatusCode.PERMISSION_DENIED,
            grpc.StatusCode.UNAUTHENTICATED,
        ):
            self.assertFalse(is_retryable_config_error(_FakeRpcError(code), established=True), code)
        self.assertFalse(is_retryable_config_error(ValueError('closed'), established=True))

    def test_describe_config_error_is_one_line(self):
        self.assertEqual(
            describe_config_error(_FakeRpcError(grpc.StatusCode.UNAVAILABLE, 'sidecar down')),
            'UNAVAILABLE: sidecar down',
        )
        self.assertEqual(describe_config_error(_FakeRpcError(grpc.StatusCode.INTERNAL)), 'INTERNAL')
        self.assertEqual(describe_config_error(ValueError('closed')), 'ValueError: closed')


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
        server.config_get_requests.clear()
        # No current values unless a test sets them, so reconnects add no handler calls.
        server.config_values = {}
        server.config_get_error = None
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
        # The client does not track this id, so it goes to the sidecar unchanged and the
        # sidecar's answer (ok=False: no such subscription) is returned.
        self.assertFalse(self.client.unsubscribe_configuration(STORE, 'not-tracked'))
        self.assertEqual(
            [r.id for r in self._fake_dapr_server.config_unsubscribe_requests], ['not-tracked']
        )

    def test_unsubscribe_while_reconnecting_stops_locally(self):
        server = self._fake_dapr_server
        server.config_stream_plans.extend(
            [
                {'id': 'first', 'end': 'abort'},
                {'id': 'second', 'updates': [{'k': 'v2'}], 'end': 'hold'},
            ]
        )
        waiting = threading.Event()

        def wait_until_stopped(watcher: ConfigurationWatcher, delay: float) -> bool:
            waiting.set()
            return watcher._stop_event.wait(WAIT_TIMEOUT_SECONDS)

        with patch.object(ConfigurationWatcher, '_wait_before_retry', wait_until_stopped):
            subscription_id = self.subscribe()
            watcher = self.watcher(subscription_id)
            self.assertTrue(waiting.wait(WAIT_TIMEOUT_SECONDS))
            self.assertIsNone(watcher.live_stream_id())

            self.assertTrue(self.client.unsubscribe_configuration(STORE, subscription_id))

        # The dead stream's id would get ok=False from the sidecar, so nothing is sent.
        self.assertEqual(server.config_unsubscribe_requests, [])
        thread = watcher._thread
        assert thread is not None
        self.assertFalse(thread.is_alive())
        self.assertNotIn((STORE, subscription_id), self.client._config_watchers)
        self.assertEqual(len(server.config_subscribe_requests), 1)

    def test_invalid_argument_after_the_subscription_was_established_is_retried(self):
        # daprd answers INVALID_ARGUMENT when the store's Subscribe fails, for example while
        # its backend is unreachable during the same outage that broke the stream.
        self._fake_dapr_server.config_stream_plans.extend(
            [
                {'id': 'first', 'updates': [{'k': 'v1'}], 'end': 'abort'},
                {'reject': grpc.StatusCode.INVALID_ARGUMENT},
                {'id': 'third', 'updates': [{'k': 'v3'}], 'end': 'hold'},
            ]
        )

        self.assertEqual(self.subscribe(), 'first')

        self.assertTrue(wait_until(lambda: len(self.updates) == 2), self.updates)
        self.assertEqual(self.updates, [('first', 'v1'), ('first', 'v3')])
        self.assertEqual(len(self._fake_dapr_server.config_subscribe_requests), 3)
        self.assertEqual(self.watcher('first').live_stream_id(), 'third')

    def test_reconnect_delivers_current_values(self):
        server = self._fake_dapr_server
        server.config_values = {'k': 'changed-while-down', 'other': 'x'}
        server.config_stream_plans.extend(
            [
                {'id': 'first', 'updates': [{'k': 'v1'}], 'end': 'abort'},
                {'id': 'second', 'end': 'hold'},
            ]
        )

        subscription_id = self.client.subscribe_configuration(
            store_name=STORE, keys=['k'], handler=self.handler, config_metadata={'m': '1'}
        )

        self.assertTrue(wait_until(lambda: len(self.updates) == 2), self.updates)
        self.assertEqual(self.updates, [('first', 'v1'), ('first', 'changed-while-down')])
        self.assertEqual(subscription_id, 'first')
        self.assertEqual(len(server.config_get_requests), 1)
        get_request = server.config_get_requests[0]
        self.assertEqual(get_request.store_name, STORE)
        self.assertEqual(list(get_request.keys), ['k'])
        self.assertEqual(dict(get_request.metadata), {'m': '1'})

    def test_first_subscribe_does_not_read_current_values(self):
        server = self._fake_dapr_server
        server.config_values = {'k': 'current'}
        server.config_stream_plans.append({'id': 'first', 'updates': [{'k': 'v1'}], 'end': 'hold'})

        self.subscribe()

        self.assertTrue(wait_until(lambda: len(self.updates) == 1), self.updates)
        time.sleep(0.2)
        self.assertEqual(self.updates, [('first', 'v1')])
        self.assertEqual(server.config_get_requests, [])

    def test_failed_current_values_read_keeps_the_subscription(self):
        server = self._fake_dapr_server
        server.config_get_error = grpc.StatusCode.INTERNAL
        server.config_stream_plans.extend(
            [
                {'id': 'first', 'updates': [{'k': 'v1'}], 'end': 'abort'},
                {'id': 'second', 'updates': [{'k': 'v2'}], 'end': 'hold'},
            ]
        )

        with self.assertLogs('dapr.clients.grpc._response', level='WARNING') as logs:
            self.subscribe()
            self.assertTrue(wait_until(lambda: len(self.updates) == 2), self.updates)

        self.assertEqual(self.updates, [('first', 'v1'), ('first', 'v2')])
        self.assertEqual(len(server.config_get_requests), 1)
        self.assertEqual(len(server.config_subscribe_requests), 2)
        self.assertTrue(
            any('Could not read the current configuration' in line for line in logs.output),
            logs.output,
        )

    def test_watcher_that_gives_up_is_removed_from_the_client(self):
        release = threading.Event()
        self._fake_dapr_server.config_stream_plans.append(
            {
                'id': 'first',
                'end': 'abort',
                'code': grpc.StatusCode.PERMISSION_DENIED,
                'wait': release,
            }
        )
        subscription_id = self.subscribe()
        self.assertIn((STORE, subscription_id), self.client._config_watchers)

        release.set()

        self.assertTrue(
            wait_until(lambda: (STORE, subscription_id) not in self.client._config_watchers)
        )

    @patch('dapr.clients.grpc._response._CONFIG_WATCHER_JOIN_TIMEOUT_SECONDS', 30.0)
    def test_stop_requested_while_opening_a_stream_cancels_it(self):
        release = threading.Event()
        self._fake_dapr_server.config_stream_plans.extend(
            [
                {'id': 'first', 'end': 'abort', 'wait': release},
                {'id': 'second', 'end': 'hold'},
            ]
        )
        subscription_id = self.subscribe()
        watcher = self.watcher(subscription_id)
        stub = self.client._stub
        real_subscribe = stub.SubscribeConfigurationAlpha1
        opened: List[_CancelRecordingCall] = []

        def subscribe_and_stop(req):
            call = _CancelRecordingCall(real_subscribe(req))
            opened.append(call)
            # stop() arrives while the watcher is opening the reconnect stream.
            watcher.request_stop()
            return call

        stub.SubscribeConfigurationAlpha1 = subscribe_and_stop
        release.set()

        self.assertTrue(wait_until(lambda: watcher.exited))
        self.assertEqual(len(opened), 1)
        self.assertTrue(opened[0].cancel_called)
        self.assertIsNone(watcher._call)
        started = time.monotonic()
        self.client.close()
        self.assertLess(time.monotonic() - started, 5.0)

    def test_reconnect_failures_are_logged_concisely_and_once_per_outage(self):
        self._fake_dapr_server.config_stream_plans.extend(
            [
                {'id': 'first', 'end': 'abort'},
                {'reject': grpc.StatusCode.UNAVAILABLE},
                {'reject': grpc.StatusCode.UNAVAILABLE},
                {'id': 'second', 'updates': [{'k': 'v2'}], 'end': 'hold'},
            ]
        )

        with self.assertLogs('dapr.clients.grpc._response', level='DEBUG') as logs:
            self.subscribe()
            self.assertTrue(wait_until(lambda: len(self.updates) == 1), self.updates)

        failures = [r for r in logs.records if 'failed, reconnecting' in r.getMessage()]
        self.assertEqual(
            [r.levelname for r in failures], ['WARNING', 'DEBUG', 'DEBUG'], logs.output
        )
        for record in failures:
            message = record.getMessage()
            self.assertNotIn('\n', message)
            self.assertNotIn('Rendezvous', message)
            self.assertIn(': UNAVAILABLE: ', message)
        self.assertTrue(
            any(
                r.levelname == 'INFO' and 'reconnected with new id second' in r.getMessage()
                for r in logs.records
            ),
            logs.output,
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
        started = time.monotonic()
        subscription_id = self.subscribe()

        self.assertIsNone(subscription_id)
        self.assertLess(time.monotonic() - started, 2.0)
        self.assertEqual(len(server.config_subscribe_requests), 1)
        self.assertEqual(self.client._config_watchers, {})
        # The watcher's own thread must exit; other tests' threads don't matter here.
        self.assertTrue(
            wait_until(
                lambda: (
                    not any(
                        t.name == f'dapr-configuration-watcher-{STORE}' and t.is_alive()
                        for t in threading.enumerate()
                    )
                )
            )
        )

    @patch('dapr.clients.grpc._response.CONFIG_STABLE_STREAM_SECONDS', 0)
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

    @patch('dapr.clients.grpc._response._CONFIG_WATCHER_JOIN_TIMEOUT_SECONDS', 30.0)
    def test_close_stops_watchers_whose_stream_cannot_be_cancelled(self):
        # gRPC client instrumentation (e.g. OpenTelemetry) wraps server streams in a plain
        # generator without cancel(); close() must still end the watcher via the channel.
        self._fake_dapr_server.config_stream_plans.append({'id': 'first', 'end': 'hold'})
        subscribe = self.client._stub.SubscribeConfigurationAlpha1
        self.client._stub.SubscribeConfigurationAlpha1 = lambda req: (r for r in subscribe(req))
        subscription_id = self.subscribe()
        watcher = self.watcher(subscription_id)
        self.assertFalse(hasattr(watcher._call, 'cancel'))
        thread = watcher._thread
        assert thread is not None

        started = time.monotonic()
        self.client.close()

        # The channel is closed before waiting on the thread, so close() doesn't sit out the
        # join timeout.
        self.assertLess(time.monotonic() - started, 10.0)
        self.assertFalse(thread.is_alive())

    def test_backoff_keeps_growing_when_streams_close_right_after_the_id(self):
        # A sidecar that accepts the subscription and closes it at once must not be
        # reconnected every CONFIG_RECONNECT_INITIAL_BACKOFF_SECONDS.
        self._fake_dapr_server.config_stream_plans.extend(
            [
                {'id': 'first', 'end': 'abort'},
                {'id': 'second', 'end': 'abort'},
                {'id': 'third', 'updates': [{'k': 'v1'}], 'end': 'hold'},
            ]
        )

        self.assertEqual(self.subscribe(), 'first')

        self.assertTrue(wait_until(lambda: len(self.updates) == 1), self.updates)
        self.assertEqual(len(self.delays), 2, self.delays)
        for delay, base in zip(self.delays, [0.5, 1.0]):
            self.assertGreaterEqual(delay, base)
            self.assertLessEqual(delay, base * 1.2)


if __name__ == '__main__':
    unittest.main()
