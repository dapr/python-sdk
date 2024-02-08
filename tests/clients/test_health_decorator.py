import unittest
from unittest.mock import patch, MagicMock
import asyncio

from dapr.clients.health import healthcheck


class TestHealthCheckDecorator(unittest.TestCase):
    @patch('urllib.request.urlopen')
    def test_healthcheck_sync(self, mock_urlopen):
        # Mock the response to simulate a healthy Dapr service
        mock_urlopen.return_value.__enter__.return_value = MagicMock(status=200)

        @healthcheck(timeout_s=1)
        def sync_test_function():
            return 'Sync function executed'

        result = sync_test_function()
        self.assertEqual(result, 'Sync function executed')
        mock_urlopen.assert_called()

    @patch('urllib.request.urlopen')
    def test_healthcheck_sync_unhealthy(self, mock_urlopen):
        # Mock the response to simulate an unhealthy Dapr service
        mock_urlopen.return_value.__enter__.return_value = MagicMock(status=500)

        @healthcheck(timeout_s=1)
        def sync_test_function():
            return 'Sync function executed'

        with self.assertRaises(TimeoutError):
            sync_test_function()

        mock_urlopen.assert_called()


class TestHealthCheckDecoratorAsync(unittest.IsolatedAsyncioTestCase):
    @patch('aiohttp.ClientSession.get')
    def test_healthcheck_async(self, mock_get):
        # Mock the response to simulate a healthy Dapr service
        mock_response = MagicMock(status=200)
        mock_get.return_value.__aenter__.return_value = mock_response

        @healthcheck(timeout_s=1)
        async def async_test_function():
            return 'Async function executed'

        async def run_test():
            result = await async_test_function()
            self.assertEqual(result, 'Async function executed')

        asyncio.run(run_test())
        mock_get.assert_called()

    # @patch('aiohttp.ClientSession.get', new_callable=AsyncMock)
    # async def test_healthcheck_async_unhealthy(self, mock_get):
    #     # Simulate an async timeout error
    #     mock_get.side_effect = asyncio.TimeoutError("Simulated async timeout")
    #
    #     @healthcheck(timeout_s=1)
    #     async def async_test_function():
    #         return "Async function executed"
    #
    #     with self.assertRaises(ValueError) as context:
    #         await async_test_function()
    #
    #     mock_get.assert_called()
