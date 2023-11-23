# -*- coding: utf-8 -*-

"""
Copyright 2023 The Dapr Authors
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

from typing import Optional

from dapr.clients.http.client import DaprHttpClient, USER_AGENT_HEADER, DAPR_USER_AGENT
from dapr.serializers import DefaultJSONSerializer


class DaprHealthClient:
    """Dapr Health Client"""

    def __init__(self, timeout: Optional[int] = 60):
        self._client = DaprHttpClient(DefaultJSONSerializer(), timeout, None, None)

    async def wait_async(self, timeout_s: int):
        """Wait for the client to become ready. If the client is already ready, this
        method returns immediately.

        Args:
            timeout_s (float): The maximum time to wait in seconds.

        Throws:
            DaprInternalError: if the timeout expires.
        """
        async def make_request() -> bool:
            _, r = await self._client.send_bytes(
                method='GET',
                headers={USER_AGENT_HEADER: DAPR_USER_AGENT},
                url=f'{self._client.get_api_url()}/healthz/outbound',
                data=None,
                query_params=None,
                timeout=timeout_s)

            return r.status >= 200 and r.status < 300

        start = time.time()
        while True:
            try:
                healthy = await make_request()
                if healthy:
                    return
            except Exception as e:
                remaining = (start + timeout_s) - time.time()
                if remaining < 0:
                    raise e  # This will be DaprInternalError as defined in http/client.py
                time.sleep(min(1, remaining))

    def wait(self, timeout_s: int):
        """Wait for the client to become ready. If the client is already ready, this
        method returns immediately.

        Args:
            timeout_s (float): The maximum time to wait in seconds.

        Throws:
            DaprInternalError: if the timeout expires.
        """
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        awaitable = self.wait_async(timeout_s)
        loop.run_until_complete(awaitable)
