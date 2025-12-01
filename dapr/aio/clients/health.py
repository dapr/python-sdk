# -*- coding: utf-8 -*-

"""
Copyright 2024 The Dapr Authors
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

import aiohttp

from dapr.clients.http.conf import DAPR_API_TOKEN_HEADER, DAPR_USER_AGENT, USER_AGENT_HEADER
from dapr.clients.http.helpers import get_api_url
from dapr.conf import settings


class DaprHealth:
    @staticmethod
    async def wait_for_sidecar():
        health_url = f'{get_api_url()}/healthz/outbound'
        headers = {USER_AGENT_HEADER: DAPR_USER_AGENT}
        if settings.DAPR_API_TOKEN is not None:
            headers[DAPR_API_TOKEN_HEADER] = settings.DAPR_API_TOKEN
        timeout = float(settings.DAPR_HEALTH_TIMEOUT)

        start = time.time()
        ssl_context = DaprHealth.get_ssl_context()

        connector = aiohttp.TCPConnector(ssl=ssl_context)
        async with aiohttp.ClientSession(connector=connector) as session:
            while True:
                try:
                    async with session.get(health_url, headers=headers) as response:
                        if 200 <= response.status < 300:
                            break
                except aiohttp.ClientError as e:
                    print(f'Health check on {health_url} failed: {e}')
                except Exception as e:
                    print(f'Unexpected error during health check: {e}')

                remaining = (start + timeout) - time.time()
                if remaining <= 0:
                    raise TimeoutError(f'Dapr health check timed out, after {timeout}.')
                await asyncio.sleep(min(1, remaining))

    @staticmethod
    def get_ssl_context():
        # This method is used (overwritten) from tests
        # to return context for self-signed certificates
        return None
