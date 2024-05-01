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
from typing import Optional, List, Callable

from grpc import RpcError, StatusCode  # type: ignore
import time

from dapr.conf import settings


class RetryPolicy:
    """RetryPolicy holds the retry policy configuration for a gRPC client.

    Args:
        max_attempts (int): The maximum number of retry attempts.
        initial_backoff (int): The initial backoff duration.
        max_backoff (int): The maximum backoff duration.
        backoff_multiplier (float): The backoff multiplier.
        retryable_http_status_codes (List[int]): The list of http retryable status codes
        retryable_grpc_status_codes (List[StatusCode]): The list of retryable grpc status codes
    """

    def __init__(
        self,
        max_attempts: Optional[int] = settings.DAPR_API_MAX_RETRIES,
        initial_backoff: int = 1,
        max_backoff: int = 20,
        backoff_multiplier: float = 1.5,
        retryable_http_status_codes: List[int] = [408, 429, 500, 502, 503, 504],
        retryable_grpc_status_codes: List[StatusCode] = [
            StatusCode.UNAVAILABLE,
            StatusCode.DEADLINE_EXCEEDED,
        ],
    ):
        if max_attempts < -1:  # type: ignore
            raise ValueError('max_attempts must be greater than or equal to -1')
        self.max_attempts = max_attempts

        if initial_backoff < 1:
            raise ValueError('initial_backoff must be greater than or equal to 1')
        self.initial_backoff = initial_backoff

        if max_backoff < 1:
            raise ValueError('max_backoff must be greater than or equal to 1')
        self.max_backoff = max_backoff

        if backoff_multiplier < 1:
            raise ValueError('backoff_multiplier must be greater than or equal to 1')
        self.backoff_multiplier = backoff_multiplier

        if len(retryable_http_status_codes) == 0:
            raise ValueError("retryable_http_status_codes can't be empty")
        self.retryable_http_status_codes = retryable_http_status_codes

        if len(retryable_grpc_status_codes) == 0:
            raise ValueError("retryable_http_status_codes can't be empty")
        self.retryable_grpc_status_codes = retryable_grpc_status_codes

    def run_rpc(self, func=Callable, *args, **kwargs):
        # If max_retries is 0, we don't retry
        if self.max_attempts == 0:
            return func(*args, **kwargs)

        attempt = 0
        while self.max_attempts == -1 or attempt < self.max_attempts:  # type: ignore
            try:
                print(f'Trying RPC call, attempt {attempt + 1}')
                return func(*args, **kwargs)
            except RpcError as err:
                if err.code() not in self.retryable_grpc_status_codes:
                    raise
                if self.max_attempts != -1 and attempt == self.max_attempts - 1:  # type: ignore
                    raise
                sleep_time = min(
                    self.max_backoff,
                    self.initial_backoff * (self.backoff_multiplier**attempt),
                )
                print(f'Sleeping for {sleep_time} seconds before retrying RPC call')
                time.sleep(sleep_time)
                attempt += 1
        raise Exception(f'RPC call failed after {attempt} retries')

    async def run_rpc_async(self, func: Callable, *args, **kwargs):
        # If max_retries is 0, we don't retry
        if self.max_attempts == 0:
            call = func(*args, **kwargs)
            result = await call
            return result, call

        attempt = 0
        while self.max_attempts == -1 or attempt < self.max_attempts:  # type: ignore
            try:
                print(f'Trying RPC call, attempt {attempt + 1}')
                call = func(*args, **kwargs)
                result = await call
                return result, call
            except RpcError as err:
                if err.code() not in self.retryable_grpc_status_codes:
                    raise
                if self.max_attempts != -1 and attempt == self.max_attempts - 1:  # type: ignore
                    raise
                sleep_time = min(
                    self.max_backoff,
                    self.initial_backoff * (self.backoff_multiplier**attempt),
                )
                print(f'Sleeping for {sleep_time} seconds before retrying RPC call')
                await asyncio.sleep(sleep_time)
                attempt += 1
        raise Exception(f'RPC call failed after {attempt} retries')

    async def make_http_call(self, session, req):
        # If max_retries is 0, we don't retry
        if self.max_attempts == 0:
            return await session.request(
                method=req['method'],
                url=req['url'],
                data=req['data'],
                headers=req['headers'],
                ssl=req['sslcontext'],
                params=req['params'],
                timeout=req['timeout'],
            )

        attempt = 0
        while self.max_attempts == -1 or attempt < self.max_attempts:  # type: ignore
            print(f'Request attempt {attempt + 1}')
            r = await session.request(
                method=req['method'],
                url=req['url'],
                data=req['data'],
                headers=req['headers'],
                ssl=req['sslcontext'],
                params=req['params'],
                timeout=req['timeout'],
            )

            if r.status not in self.retryable_http_status_codes:
                return r

            if (
                self.max_attempts != -1 and attempt == self.max_attempts - 1  # type: ignore
            ):  # type: ignore
                return r

            sleep_time = min(
                self.max_backoff,
                self.initial_backoff * (self.backoff_multiplier**attempt),
            )

            print(f'Sleeping for {sleep_time} seconds before retrying call')
            await asyncio.sleep(sleep_time)
            attempt += 1
