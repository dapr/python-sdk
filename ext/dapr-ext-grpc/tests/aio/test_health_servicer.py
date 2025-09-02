import unittest
from unittest.mock import AsyncMock, Mock

from dapr.ext.grpc.aio._health_servicer import _AioHealthCheckServicer


class OnInvokeTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self._health_servicer = _AioHealthCheckServicer()

    async def test_healthcheck_cb_called(self):
        health_cb = AsyncMock()
        self._health_servicer.register_health_check(health_cb)
        await self._health_servicer.HealthCheck(None, Mock())
        health_cb.assert_called_once()

    async def test_no_healthcheck_cb(self):
        with self.assertRaises(NotImplementedError) as exception_context:
            await self._health_servicer.HealthCheck(None, Mock())
        self.assertIn('Method not implemented!', exception_context.exception.args[0])
