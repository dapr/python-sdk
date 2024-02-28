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
        retryable_status_codes (List[StatusCode]): The list of status codes that are retryable.
    """

    def __init__(
        self,
        max_attempts: Optional[int] = settings.DAPR_API_MAX_RETRIES,
        initial_backoff: int = 1,
        max_backoff: int = 20,
        backoff_multiplier: float = 1.5,
        retryable_status_codes: List[StatusCode] = [
            StatusCode.UNAVAILABLE,
            StatusCode.DEADLINE_EXCEEDED,
        ],
    ):
        self.max_attempts = max_attempts
        self.initial_backoff = initial_backoff
        self.max_backoff = max_backoff
        self.backoff_multiplier = backoff_multiplier
        self.retryable_status_codes = retryable_status_codes


def run_rpc_with_retry(policy: RetryPolicy, func=Callable, *args, **kwargs):
    # If max_retries is 0, we don't retry
    if policy.max_attempts == 0:
        return func(*args, **kwargs)

    attempt = 0
    while policy.max_attempts == -1 or attempt < policy.max_attempts:  # type: ignore
        try:
            print(f'Trying RPC call, attempt {attempt + 1}')
            return func(*args, **kwargs)
        except RpcError as err:
            if err.code() not in policy.retryable_status_codes:
                raise
            if policy.max_attempts != -1 and attempt == policy.max_attempts - 1:  # type: ignore
                raise
            sleep_time = min(
                policy.max_backoff,
                policy.initial_backoff * (policy.backoff_multiplier**attempt),
            )
            print(f'Sleeping for {sleep_time} seconds before retrying RPC call')
            time.sleep(sleep_time)
            attempt += 1
    raise Exception(f'RPC call failed after {attempt} retries')


async def async_run_rpc_with_retry(policy: RetryPolicy, func: Callable, *args, **kwargs):
    # If max_retries is 0, we don't retry
    if policy.max_attempts == 0:
        call = func(*args, **kwargs)
        result = await call
        return result, call

    attempt = 0
    while policy.max_attempts == -1 or attempt < policy.max_attempts:  # type: ignore
        try:
            print(f'Trying RPC call, attempt {attempt + 1}')
            call = func(*args, **kwargs)
            result = await call
            return result, call
        except RpcError as err:
            if err.code() not in policy.retryable_status_codes:
                raise
            if policy.max_attempts != -1 and attempt == policy.max_attempts - 1:  # type: ignore
                raise
            sleep_time = min(
                policy.max_backoff,
                policy.initial_backoff * (policy.backoff_multiplier**attempt),
            )
            print(f'Sleeping for {sleep_time} seconds before retrying RPC call')
            await asyncio.sleep(sleep_time)
            attempt += 1
    raise Exception(f'RPC call failed after {attempt} retries')
