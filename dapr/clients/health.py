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
import urllib.request
import urllib.error
import time

from dapr.clients.http.conf import DAPR_API_TOKEN_HEADER, USER_AGENT_HEADER, DAPR_USER_AGENT
from dapr.clients.http.helpers import get_api_url
from dapr.conf import settings


# def healthcheck():
#     def decorator(func):
#         timeout = settings.DAPR_HEALTH_TIMEOUT
#         health_url = f'{get_api_url()}/healthz/outbound'
#         headers = {USER_AGENT_HEADER: DAPR_USER_AGENT}
#         if settings.DAPR_API_TOKEN is not None:
#             headers[DAPR_API_TOKEN_HEADER] = settings.DAPR_API_TOKEN
#         start = time.time()
#
#         @wraps(func)
#         async def async_wrapper(*args, **kwargs):
#             # Async health check logic
#             async with aiohttp.ClientSession() as session:
#                 while True:
#                     try:
#                         async with session.get(health_url, headers=headers) as response:
#                             if 200 <= response.status < 300:
#                                 break
#                     except aiohttp.ClientError as e:
#                         print(f'Health check failed: {e}')
#
#                     remaining = (start + timeout) - time.time()
#                     if remaining <= 0:
#                         raise TimeoutError(f'Dapr health check timed out, after {timeout}.')
#                     await asyncio.sleep(min(1, remaining))
#             return await func(*args, **kwargs)
#
#         def sync_wrapper(*args, **kwargs):
#             while True:
#                 try:
#                     req = urllib.request.Request(health_url, headers=headers)
#                     with urllib.request.urlopen(req) as response:
#                         if 200 <= response.status < 300:
#                             break
#                 except urllib.error.URLError as e:
#                     print(f'Health check on {health_url} failed: {e.reason}')
#
#                 remaining = (start + timeout) - time.time()
#                 if remaining <= 0:
#                     raise TimeoutError(f'Dapr health check timed out, after {timeout}.')
#                 time.sleep(min(1, remaining))
#             return func(*args, **kwargs)
#
#         if inspect.iscoroutinefunction(func):
#             return async_wrapper
#         else:
#             return sync_wrapper
#
#     return decorator


class CheckDaprHealth:
    def __init__(self):
        self.health_url = f'{get_api_url()}/healthz/outbound'
        self.headers = {USER_AGENT_HEADER: DAPR_USER_AGENT}
        if settings.DAPR_API_TOKEN is not None:
            self.headers[DAPR_API_TOKEN_HEADER] = settings.DAPR_API_TOKEN
        self.timeout = settings.DAPR_HEALTH_TIMEOUT

        start = time.time()
        while True:
            try:
                req = urllib.request.Request(self.health_url, headers=self.headers)
                with urllib.request.urlopen(req) as response:
                    if 200 <= response.status < 300:
                        break
            except urllib.error.URLError as e:
                print(f'Health check on {self.health_url} failed: {e.reason}')

            remaining = (start + self.timeout) - time.time()
            if remaining <= 0:
                raise TimeoutError(f'Dapr health check timed out, after {self.timeout}.')
            time.sleep(min(1, remaining))
