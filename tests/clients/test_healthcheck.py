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

import socket
import threading
import time
import unittest
from unittest.mock import MagicMock, patch

from dapr.clients.health import DaprHealth
from dapr.conf import settings
from dapr.version import __version__


class DaprHealthCheckTests(unittest.TestCase):
    @patch.object(settings, 'DAPR_HTTP_ENDPOINT', 'http://domain.com:3500')
    @patch('urllib.request.urlopen')
    def test_wait_for_sidecar_success(self, mock_urlopen):
        mock_urlopen.return_value.__enter__.return_value = MagicMock(status=200)

        try:
            DaprHealth.wait_for_sidecar()
        except Exception as e:
            self.fail(f'wait_for_sidecar() raised an exception unexpectedly: {e}')

        mock_urlopen.assert_called_once()

        called_url = mock_urlopen.call_args[0][0].full_url
        self.assertEqual(called_url, 'http://domain.com:3500/v1.0/healthz/outbound')

        # Check headers are properly set
        headers = mock_urlopen.call_args[0][0].headers
        self.assertIn('User-agent', headers)
        self.assertEqual(headers['User-agent'], f'dapr-sdk-python/{__version__}')

    @patch.object(settings, 'DAPR_HTTP_ENDPOINT', 'http://domain.com:3500')
    @patch.object(settings, 'DAPR_API_TOKEN', 'mytoken')
    @patch('urllib.request.urlopen')
    def test_wait_for_sidecar_success_with_api_token(self, mock_urlopen):
        mock_urlopen.return_value.__enter__.return_value = MagicMock(status=200)

        try:
            DaprHealth.wait_for_sidecar()
        except Exception as e:
            self.fail(f'wait_for_sidecar() raised an exception unexpectedly: {e}')

        mock_urlopen.assert_called_once()

        # Check headers are properly set
        headers = mock_urlopen.call_args[0][0].headers
        self.assertIn('User-agent', headers)
        self.assertEqual(headers['User-agent'], f'dapr-sdk-python/{__version__}')
        self.assertIn('Dapr-api-token', headers)
        self.assertEqual(headers['Dapr-api-token'], 'mytoken')

    @patch.object(settings, 'DAPR_HEALTH_TIMEOUT', '2.5')
    @patch('urllib.request.urlopen')
    def test_wait_for_sidecar_timeout(self, mock_urlopen):
        mock_urlopen.return_value.__enter__.return_value = MagicMock(status=500)

        start = time.time()

        with self.assertRaises(TimeoutError):
            DaprHealth.wait_for_sidecar()

        self.assertGreaterEqual(time.time() - start, 2.5)
        self.assertGreater(mock_urlopen.call_count, 1)


def listen_without_replying(test: unittest.TestCase) -> int:
    """Open a local port that accepts connections (the OS completes the handshake from
    the listen backlog) but never sends a reply, like a hung sidecar. Returns the port."""
    listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    test.addCleanup(listener.close)
    listener.bind(('127.0.0.1', 0))
    listener.listen(16)
    return listener.getsockname()[1]


class DaprHealthCheckUnresponsiveSidecarTests(unittest.TestCase):
    # How long the test waits before calling wait_for_sidecar() hung. Well above
    # DAPR_HEALTH_TIMEOUT so a slow CI machine does not fail it.
    HANG_LIMIT_SECONDS = 15

    @patch.object(settings, 'DAPR_HEALTH_TIMEOUT', '1')
    def test_wait_for_sidecar_times_out_when_sidecar_never_replies(self):
        port = listen_without_replying(self)
        outcome = {}

        def wait():
            try:
                DaprHealth.wait_for_sidecar()
            except Exception as error:
                outcome['error'] = error

        with patch.object(settings, 'DAPR_HTTP_ENDPOINT', f'http://127.0.0.1:{port}'):
            # Run in a daemon thread so a regression fails this test instead of hanging
            # the whole session.
            waiter = threading.Thread(target=wait, daemon=True)
            start = time.time()
            waiter.start()
            waiter.join(self.HANG_LIMIT_SECONDS)

        self.assertFalse(waiter.is_alive(), 'wait_for_sidecar() blocked past DAPR_HEALTH_TIMEOUT')
        self.assertIsInstance(outcome.get('error'), TimeoutError)
        self.assertIn('Dapr health check timed out', str(outcome['error']))
        self.assertLess(time.time() - start, self.HANG_LIMIT_SECONDS)
