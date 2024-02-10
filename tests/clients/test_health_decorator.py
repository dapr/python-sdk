import asyncio
import unittest
from unittest.mock import patch, MagicMock

from dapr.clients import health


class TestHealthCheckDecorator(unittest.TestCase):
    @patch('urllib.request.urlopen')
    def test_healthcheck_sync(self, mock_urlopen):
        # Mock the response to simulate a healthy Dapr service
        mock_urlopen.return_value.__enter__.return_value = MagicMock(status=200)

        health.HEALTHY = False

        @health.healthcheck()
        def sync_test_function():
            return 'Sync function executed'

        result = sync_test_function()
        self.assertEqual(result, 'Sync function executed')
        mock_urlopen.assert_called()

    @patch('urllib.request.urlopen')
    def test_healthcheck_sync_unhealthy(self, mock_urlopen):
        # Mock the response to simulate an unhealthy Dapr service

        mock_urlopen.return_value.__enter__.return_value = MagicMock(status=500)

        health.HEALTHY = False

        @health.healthcheck()
        def sync_test_function():
            return 'Sync function executed'

        with self.assertRaises(TimeoutError):
            sync_test_function()

        mock_urlopen.assert_called()

    @patch('urllib.request.urlopen')
    def test_healthcheck_sync_unhealthy_with_global_healthy(self, mock_urlopen):
        # Mock the response to simulate an unhealthy Dapr service
        mock_urlopen.return_value.__enter__.return_value = MagicMock(status=500)

        health.HEALTHY = True

        @health.healthcheck()
        def sync_test_function():
            return 'Sync function executed'

        sync_test_function()

        # Assert we never called the health endpoint, because the global var has already been set
        mock_urlopen.assert_not_called()


class TestHealthCheckDecoratorAsync(unittest.IsolatedAsyncioTestCase):
    @patch('aiohttp.ClientSession.get')
    def test_healthcheck_async(self, mock_get):
        # Mock the response to simulate a healthy Dapr service
        mock_response = MagicMock(status=200)
        mock_get.return_value.__aenter__.return_value = mock_response

        health.HEALTHY = False

        @health.healthcheck()
        async def async_test_function():
            return 'Async function executed'

        async def run_test():
            result = await async_test_function()
            self.assertEqual(result, 'Async function executed')

        asyncio.run(run_test())
        mock_get.assert_called()

    @patch('aiohttp.ClientSession.get')
    def test_healthcheck_async_unhealthy(self, mock_get):
        # Mock the response to simulate an unhealthy Dapr service
        mock_response = MagicMock(status=500)
        mock_get.return_value.__aenter__.return_value = mock_response

        health.HEALTHY = False

        @health.healthcheck()
        async def async_test_function():
            return 'Async function executed'

        async def run_test():
            with self.assertRaises(TimeoutError):
                await async_test_function()

        asyncio.run(run_test())
        mock_get.assert_called()

    @patch('aiohttp.ClientSession.get')
    def test_healthcheck_async_unhealthy_with_global(self, mock_get):
        # Mock the response to simulate an unhealthy Dapr service
        mock_response = MagicMock(status=500)
        mock_get.return_value.__aenter__.return_value = mock_response

        health.HEALTHY = True

        @health.healthcheck()
        async def async_test_function():
            return 'Async function executed'

        async def run_test():
            await async_test_function()

        asyncio.run(run_test())
        mock_get.assert_not_called()
