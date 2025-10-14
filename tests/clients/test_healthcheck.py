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
import time
import unittest
from unittest.mock import patch, MagicMock

from dapr.clients.health import DaprHealth
from dapr.conf import settings
from dapr.version import __version__


class DaprHealthCheckTests(unittest.TestCase):
    @patch.object(settings, 'DAPR_HTTP_ENDPOINT', 'http://domain.com:3500')
    @patch('urllib.request.urlopen')
    def test_wait_until_ready_success(self, mock_urlopen):
        mock_urlopen.return_value.__enter__.return_value = MagicMock(status=200)

        try:
            DaprHealth.wait_until_ready()
        except Exception as e:
            self.fail(f'wait_until_ready() raised an exception unexpectedly: {e}')

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
    def test_wait_until_ready_success_with_api_token(self, mock_urlopen):
        mock_urlopen.return_value.__enter__.return_value = MagicMock(status=200)

        try:
            DaprHealth.wait_until_ready()
        except Exception as e:
            self.fail(f'wait_until_ready() raised an exception unexpectedly: {e}')

        mock_urlopen.assert_called_once()

        # Check headers are properly set
        headers = mock_urlopen.call_args[0][0].headers
        self.assertIn('User-agent', headers)
        self.assertEqual(headers['User-agent'], f'dapr-sdk-python/{__version__}')
        self.assertIn('Dapr-api-token', headers)
        self.assertEqual(headers['Dapr-api-token'], 'mytoken')

    @patch.object(settings, 'DAPR_HEALTH_TIMEOUT', '2.5')
    @patch('urllib.request.urlopen')
    def test_wait_until_ready_timeout(self, mock_urlopen):
        mock_urlopen.return_value.__enter__.return_value = MagicMock(status=500)

        start = time.time()

        with self.assertRaises(TimeoutError):
            DaprHealth.wait_until_ready()

        self.assertGreaterEqual(time.time() - start, 2.5)
        self.assertGreater(mock_urlopen.call_count, 1)
