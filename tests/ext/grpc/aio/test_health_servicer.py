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

import unittest
from unittest.mock import AsyncMock, MagicMock

from dapr.ext.grpc.aio._health_servicer import _AioHealthCheckServicer


class HealthCheckTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self._health_servicer = _AioHealthCheckServicer()

    async def test_async_healthcheck_cb_awaited(self):
        health_cb = AsyncMock()
        self._health_servicer.register_health_check(health_cb)

        await self._health_servicer.HealthCheck(None, MagicMock())

        health_cb.assert_awaited_once()

    async def test_sync_healthcheck_cb_called(self):
        """`register_health_check(lambda: None)` keeps working on the aio app."""
        health_cb = MagicMock()
        self._health_servicer.register_health_check(health_cb)

        await self._health_servicer.HealthCheck(None, MagicMock())

        health_cb.assert_called_once()

    async def test_no_healthcheck_cb(self):
        with self.assertRaises(NotImplementedError) as exception_context:
            await self._health_servicer.HealthCheck(None, MagicMock())

        self.assertIn('Method not implemented!', exception_context.exception.args[0])

    def test_falsy_healthcheck_cb_rejected(self):
        with self.assertRaises(ValueError):
            self._health_servicer.register_health_check(None)


if __name__ == '__main__':
    unittest.main()
