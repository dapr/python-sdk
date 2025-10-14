# -*- coding: utf-8 -*-

"""
Copyright 2025 The Dapr Authors
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
import time
import unittest
from unittest.mock import patch, MagicMock

from dapr.aio.clients.health import DaprHealth
from dapr.conf import settings
from dapr.version import __version__


class DaprHealthCheckAsyncTests(unittest.IsolatedAsyncioTestCase):
    @patch.object(settings, 'DAPR_HTTP_ENDPOINT', 'http://domain.com:3500')
    @patch('urllib.request.urlopen')
    async def test_wait_until_ready_success(self, mock_urlopen):
        mock_urlopen.return_value.__enter__.return_value = MagicMock(status=200)

        try:
            await DaprHealth.wait_until_ready()
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
    async def test_wait_until_ready_success_with_api_token(self, mock_urlopen):
        mock_urlopen.return_value.__enter__.return_value = MagicMock(status=200)

        try:
            await DaprHealth.wait_until_ready()
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
    async def test_wait_until_ready_timeout(self, mock_urlopen):
        mock_urlopen.return_value.__enter__.return_value = MagicMock(status=500)

        start = time.time()

        with self.assertRaises(TimeoutError):
            await DaprHealth.wait_until_ready()

        self.assertGreaterEqual(time.time() - start, 2.5)
        self.assertGreater(mock_urlopen.call_count, 1)

    @patch.object(settings, 'DAPR_HTTP_ENDPOINT', 'http://domain.com:3500')
    @patch.object(settings, 'DAPR_HEALTH_TIMEOUT', '5.0')
    @patch('urllib.request.urlopen')
    async def test_health_check_does_not_block(self, mock_urlopen):
        """Test that health check doesn't block other async tasks from running"""
        # Mock health check to retry several times before succeeding
        call_count = [0]  # Use list to allow modification in nested function

        class MockResponse:
            def __init__(self, status):
                self.status = status

            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc_val, exc_tb):
                return None

        def side_effect(*args, **kwargs):
            call_count[0] += 1
            # First 2 calls fail with URLError, then succeed
            # This will cause ~2 seconds of retries (1 second sleep after each failure)
            if call_count[0] <= 2:
                import urllib.error
                raise urllib.error.URLError('Connection refused')
            else:
                return MockResponse(status=200)

        mock_urlopen.side_effect = side_effect

        # Counter that will be incremented by background task
        counter = [0]  # Use list to allow modification in nested function
        is_running = [True]

        async def increment_counter():
            """Background task that increments counter every 0.5 seconds"""
            while is_running[0]:
                await asyncio.sleep(0.5)
                counter[0] += 1

        # Start the background task
        counter_task = asyncio.create_task(increment_counter())

        try:
            # Run health check (will take ~2 seconds with retries)
            await DaprHealth.wait_until_ready()

            # Stop the background task
            is_running[0] = False
            await asyncio.sleep(0.1)  # Give it time to finish current iteration

            # Verify the counter was incremented during health check
            # In 2 seconds with 0.5s intervals, we expect at least 3 increments
            self.assertGreaterEqual(
                counter[0],
                3,
                f'Expected counter to increment at least 3 times during health check, '
                f'but got {counter[0]}. This indicates health check may be blocking.',
            )

            # Verify health check made multiple attempts
            self.assertGreaterEqual(call_count[0], 2)

        finally:
            # Clean up
            is_running[0] = False
            counter_task.cancel()
            try:
                await counter_task
            except asyncio.CancelledError:
                pass

    @patch.object(settings, 'DAPR_HTTP_ENDPOINT', 'http://domain.com:3500')
    @patch('urllib.request.urlopen')
    async def test_multiple_health_checks_concurrent(self, mock_urlopen):
        """Test that multiple health check calls can run concurrently"""
        mock_urlopen.return_value.__enter__.return_value = MagicMock(status=200)

        # Run multiple health checks concurrently
        start_time = time.time()
        results = await asyncio.gather(
            DaprHealth.wait_until_ready(),
            DaprHealth.wait_until_ready(),
            DaprHealth.wait_until_ready(),
        )
        elapsed = time.time() - start_time

        # All should complete successfully
        self.assertEqual(len(results), 3)
        self.assertIsNone(results[0])
        self.assertIsNone(results[1])
        self.assertIsNone(results[2])

        # Should complete quickly since they run concurrently
        self.assertLess(elapsed, 1.0)

        # Verify multiple calls were made
        self.assertGreaterEqual(mock_urlopen.call_count, 3)


if __name__ == '__main__':
    unittest.main()
