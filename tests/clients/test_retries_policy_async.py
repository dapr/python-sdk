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
import unittest
from unittest import mock
from unittest.mock import MagicMock, patch, AsyncMock

from grpc import StatusCode, RpcError

from dapr.clients.retry import RetryPolicy


class RetryPolicyGrpcAsyncTests(unittest.IsolatedAsyncioTestCase):
    async def test_run_rpc_async_with_retry_success(self):
        mock_func = AsyncMock(return_value='success')

        policy = RetryPolicy(max_attempts=3, retryable_grpc_status_codes=[StatusCode.UNAVAILABLE])
        result, _ = await policy.run_rpc_async(mock_func, 'foo', arg1=1, arg2=2)

        self.assertEqual(result, 'success')
        mock_func.assert_awaited_once_with('foo', arg1=1, arg2=2)

    async def test_run_rpc_async_with_retry_no_retry(self):
        mock_error = RpcError()
        mock_error.code = MagicMock(return_value=StatusCode.UNAVAILABLE)
        mock_func = AsyncMock(side_effect=mock_error)

        with self.assertRaises(RpcError):
            policy = RetryPolicy(max_attempts=0)
            await policy.run_rpc_async(mock_func)
        mock_func.assert_awaited_once()

    @patch('asyncio.sleep', return_value=None)
    async def test_run_rpc_async_with_retry_fail(self, mock_sleep):
        mock_error = RpcError()
        mock_error.code = MagicMock(return_value=StatusCode.UNAVAILABLE)
        mock_func = AsyncMock(side_effect=mock_error)
        with self.assertRaises(RpcError):
            policy = RetryPolicy(max_attempts=4, initial_backoff=2, backoff_multiplier=1.5)
            await policy.run_rpc_async(mock_func)

        self.assertEqual(mock_func.await_count, 4)
        expected_sleep_calls = [
            mock.call(2.0),  # First sleep call
            mock.call(3.0),  # Second sleep call
            mock.call(4.5),  # Third sleep call
        ]
        mock_sleep.assert_has_calls(expected_sleep_calls, any_order=False)

    async def test_run_rpc_async_with_retry_fail_with_another_status_code(self):
        mock_error = RpcError()
        mock_error.code = MagicMock(return_value=StatusCode.FAILED_PRECONDITION)
        mock_func = AsyncMock(side_effect=mock_error)

        with self.assertRaises(RpcError):
            policy = RetryPolicy(
                max_attempts=3, retryable_grpc_status_codes=[StatusCode.UNAVAILABLE]
            )
            await policy.run_rpc_async(mock_func)

        mock_func.assert_awaited_once()

    @patch('asyncio.sleep', return_value=None)
    async def test_run_rpc_async_with_retry_fail_with_max_backoff(self, mock_sleep):
        mock_error = RpcError()
        mock_error.code = MagicMock(return_value=StatusCode.UNAVAILABLE)
        mock_func = AsyncMock(side_effect=mock_error)

        with self.assertRaises(RpcError):
            policy = RetryPolicy(
                max_attempts=4, initial_backoff=2, backoff_multiplier=1.5, max_backoff=3
            )
            await policy.run_rpc_async(mock_func)

        self.assertEqual(mock_func.await_count, 4)
        expected_sleep_calls = [
            mock.call(2.0),  # First sleep call
            mock.call(3.0),  # Second sleep call
            mock.call(3.0),  # Third sleep call
        ]
        mock_sleep.assert_has_calls(expected_sleep_calls, any_order=False)

    @patch('asyncio.sleep', return_value=None)
    async def test_run_rpc_async_with_infinite_retries(self, mock_sleep):
        # Testing a function that's supposed to run forever is tricky, so we'll simulate it
        # Instead of a fixed side effect, we'll create a function that's supposed to
        # break out of the cycle after X calls.
        # Then we assert that the function was called X times before breaking the loop

        # Configure the policy to simulate infinite retries
        policy = RetryPolicy(max_attempts=-1, retryable_grpc_status_codes=[StatusCode.UNAVAILABLE])

        mock_error = RpcError()
        mock_error.code = MagicMock(return_value=StatusCode.UNAVAILABLE)
        mock_func = AsyncMock()

        # Use a side effect on the mock to count calls and eventually interrupt the loop
        call_count = 0

        def side_effect(*args, **kwargs):
            nonlocal call_count
            call_count += 1

            if call_count >= 10:  # Five calls before breaking the loop
                raise Exception('Test interrupt')

            raise mock_error

        mock_func.side_effect = side_effect

        # Run the test, expecting the custom exception to break the loop
        with self.assertRaises(Exception) as context:
            await policy.run_rpc_async(mock_func)

        self.assertEqual(str(context.exception), 'Test interrupt')

        # Verify the function was retried the expected number of times before interrupting
        self.assertEqual(call_count, 10)
