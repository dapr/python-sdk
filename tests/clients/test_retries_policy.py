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
from unittest.mock import Mock, MagicMock, patch, AsyncMock

from grpc import StatusCode, RpcError

from dapr.clients.retry import RetryPolicy
from dapr.serializers import DefaultJSONSerializer


class RetryPolicyTests(unittest.TestCase):
    async def httpSetUp(self):
        # Setup your test environment and mocks here
        self.session = MagicMock()
        self.session.request = AsyncMock()

        self.serializer = (DefaultJSONSerializer(),)

        # Example request
        self.req = {
            'method': 'GET',
            'url': 'http://example.com',
            'data': None,
            'headers': None,
            'sslcontext': None,
            'params': None,
            'timeout': None,
        }

    def test_init_success_default(self):
        policy = RetryPolicy()

        self.assertEqual(0, policy.max_attempts)
        self.assertEqual(1, policy.initial_backoff)
        self.assertEqual(20, policy.max_backoff)
        self.assertEqual(1.5, policy.backoff_multiplier)
        self.assertEqual([408, 429, 500, 502, 503, 504], policy.retryable_http_status_codes)
        self.assertEqual(
            [StatusCode.UNAVAILABLE, StatusCode.DEADLINE_EXCEEDED],
            policy.retryable_grpc_status_codes,
        )

    def test_init_success(self):
        policy = RetryPolicy(
            max_attempts=3,
            initial_backoff=2,
            max_backoff=10,
            backoff_multiplier=2,
            retryable_grpc_status_codes=[StatusCode.UNAVAILABLE],
            retryable_http_status_codes=[408, 429],
        )
        self.assertEqual(3, policy.max_attempts)
        self.assertEqual(2, policy.initial_backoff)
        self.assertEqual(10, policy.max_backoff)
        self.assertEqual(2, policy.backoff_multiplier)
        self.assertEqual([StatusCode.UNAVAILABLE], policy.retryable_grpc_status_codes)
        self.assertEqual([408, 429], policy.retryable_http_status_codes)

    def test_init_with_errors(self):
        with self.assertRaises(ValueError):
            RetryPolicy(max_attempts=-2)

        with self.assertRaises(ValueError):
            RetryPolicy(initial_backoff=0)

        with self.assertRaises(ValueError):
            RetryPolicy(max_backoff=0)

        with self.assertRaises(ValueError):
            RetryPolicy(backoff_multiplier=0)

        with self.assertRaises(ValueError):
            RetryPolicy(retryable_http_status_codes=[])

        with self.assertRaises(ValueError):
            RetryPolicy(retryable_grpc_status_codes=[])

    def test_run_rpc_with_retry_success(self):
        mock_func = Mock(return_value='success')

        policy = RetryPolicy(max_attempts=3, retryable_grpc_status_codes=[StatusCode.UNAVAILABLE])
        result = policy.run_rpc(mock_func, 'foo', 'bar', arg1=1, arg2=2)

        self.assertEqual(result, 'success')
        mock_func.assert_called_once_with('foo', 'bar', arg1=1, arg2=2)

    def test_run_rpc_with_retry_no_retry(self):
        mock_error = RpcError()
        mock_error.code = MagicMock(return_value=StatusCode.UNAVAILABLE)
        mock_func = MagicMock(side_effect=mock_error)

        policy = RetryPolicy(max_attempts=0)
        with self.assertRaises(RpcError):
            policy.run_rpc(mock_func)
        mock_func.assert_called_once()

    @patch('time.sleep', return_value=None)  # To speed up tests
    def test_run_rpc_with_retry_fail(self, mock_sleep):
        mock_error = RpcError()
        mock_error.code = MagicMock(return_value=StatusCode.UNAVAILABLE)
        mock_func = MagicMock(side_effect=mock_error)
        with self.assertRaises(RpcError):
            policy = RetryPolicy(max_attempts=4, initial_backoff=2, backoff_multiplier=1.5)
            policy.run_rpc(mock_func)

        self.assertEqual(mock_func.call_count, 4)
        expected_sleep_calls = [
            mock.call(2.0),  # First sleep call
            mock.call(3.0),  # Second sleep call
            mock.call(4.5),  # Third sleep call
        ]
        mock_sleep.assert_has_calls(expected_sleep_calls, any_order=False)

    def test_run_rpc_with_retry_fail_with_another_status_code(self):
        mock_error = RpcError()
        mock_error.code = MagicMock(return_value=StatusCode.FAILED_PRECONDITION)
        mock_func = MagicMock(side_effect=mock_error)

        with self.assertRaises(RpcError):
            policy = RetryPolicy(
                max_attempts=3, retryable_grpc_status_codes=[StatusCode.UNAVAILABLE]
            )
            policy.run_rpc(mock_func)

        mock_func.assert_called_once()

    @patch('time.sleep', return_value=None)  # To speed up tests
    def test_run_rpc_with_retry_fail_with_max_backoff(self, mock_sleep):
        mock_error = RpcError()
        mock_error.code = MagicMock(return_value=StatusCode.UNAVAILABLE)
        mock_func = MagicMock(side_effect=mock_error)
        with self.assertRaises(RpcError):
            policy = RetryPolicy(
                max_attempts=4, initial_backoff=2, backoff_multiplier=1.5, max_backoff=3
            )
            policy.run_rpc(
                mock_func,
            )

        self.assertEqual(mock_func.call_count, 4)
        expected_sleep_calls = [
            mock.call(2.0),  # First sleep call
            mock.call(3.0),  # Second sleep call
            mock.call(3.0),  # Third sleep call
        ]
        mock_sleep.assert_has_calls(expected_sleep_calls, any_order=False)

    @patch('time.sleep', return_value=None)  # To speed up tests
    def test_run_rpc_with_infinite_retries(self, mock_sleep):
        # Testing a function that's supposed to run forever is tricky, so we'll simulate it
        # Instead of a fixed side effect, we'll create a function that's supposed to
        # break out of the cycle after X calls.
        # Then we assert that the function was called X times before breaking the loop

        # Configure the policy to simulate infinite retries
        policy = RetryPolicy(max_attempts=-1, retryable_grpc_status_codes=[StatusCode.UNAVAILABLE])

        mock_error = RpcError()
        mock_error.code = MagicMock(return_value=StatusCode.UNAVAILABLE)
        mock_func = MagicMock()

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
            policy.run_rpc(mock_func)

        self.assertEqual(str(context.exception), 'Test interrupt')

        # Verify the function was retried the expected number of times before interrupting
        self.assertEqual(call_count, 10)

    # Test retrying async rpc calls
    async def test_run_rpc_async_with_retry_success(self):
        mock_func = AsyncMock(return_value='success')

        policy = RetryPolicy(max_attempts=3, retryable_grpc_status_codes=[StatusCode.UNAVAILABLE])
        result, _ = await policy.async_run_rpc(mock_func, 'foo', arg1=1, arg2=2)

        self.assertEqual(result, 'success')
        mock_func.assert_awaited_once_with('foo', arg1=1, arg2=2)

    async def test_run_rpc_async_with_retry_no_retry(self):
        mock_error = RpcError()
        mock_error.code = MagicMock(return_value=StatusCode.UNAVAILABLE)
        mock_func = AsyncMock(side_effect=mock_error)

        with self.assertRaises(RpcError):
            policy = RetryPolicy(max_attempts=0)
            await policy.async_run_rpc(mock_func)
        mock_func.assert_awaited_once()

    # Test retrying http requests
    async def test_http_call_with_success(self):
        # Mock the request to succeed on the first try
        self.session.request.return_value.status = 200

        policy = RetryPolicy()
        response = await policy.make_http_call(self.session, self.req)

        self.session.request.assert_called_once()
        self.assertEqual(200, response.status)

    async def test_http_call_success_with_no_retry(self):
        self.session.request.return_value.status = 200

        policy = RetryPolicy(max_attempts=0)
        response = await policy.make_http_call(self.session, self.req)

        self.session.request.assert_called_once()
        self.assertEqual(200, response.status)

    async def test_http_call_fail_with_no_retry(self):
        self.session.request.return_value.status = 408

        policy = RetryPolicy(max_attempts=0)
        response = await policy.make_http_call(self.session, self.req)

        self.session.request.assert_called_once()
        self.assertEqual(408, response.status)

    @patch('asyncio.sleep', return_value=None)
    async def test_http_call_retry_eventually_succeeds(self, _):
        # Mock the request to fail twice then succeed
        self.session.request.side_effect = [
            MagicMock(status=500),  # First attempt fails
            MagicMock(status=502),  # Second attempt fails
            MagicMock(status=200),  # Third attempt succeeds
        ]

        policy = RetryPolicy(max_attempts=3)
        response = await policy.make_http_call(self.session, self.req)

        self.assertEqual(3, self.session.request.call_count)
        self.assertEqual(200, response.status)

    @patch('asyncio.sleep', return_value=None)
    async def test_http_call_retry_eventually_fails(self, _):
        self.session.request.return_value.status = 408

        policy = RetryPolicy(max_attempts=3)
        response = await policy.make_http_call(self.session, self.req)

        self.assertEqual(3, self.session.request.call_count)
        self.assertEqual(408, response.status)

    @patch('asyncio.sleep', return_value=None)
    async def test_http_call_retry_fails_with_a_different_code(self, _):
        # Mock the request to fail twice then succeed
        self.session.request.return_value.status = 501

        policy = RetryPolicy(max_attempts=3, retryable_http_status_codes=[500])
        response = await policy.make_http_call(self.session, self.req)

        self.session.request.assert_called_once()
        self.assertEqual(response.status, 501)

    @patch('asyncio.sleep', return_value=None)
    async def test_http_call_retries_exhausted(self, _):
        # Mock the request to fail three times
        self.session.request.return_value = MagicMock(status=500)

        policy = RetryPolicy(max_attempts=3, retryable_http_status_codes=[500])
        response = await policy.make_http_call(self.session, self.req)

        self.assertEqual(3, self.session.request.call_count)
        self.assertEqual(500, response.status)

    @patch('asyncio.sleep', return_value=None)
    async def test_http_call_max_backoff(self, mock_sleep):
        self.session.request.return_value.status = 500

        policy = RetryPolicy(max_attempts=4, initial_backoff=2, backoff_multiplier=2, max_backoff=3)
        response = await policy.make_http_call(self.session, self.req)

        expected_sleep_calls = [
            mock.call(2.0),  # First sleep call
            mock.call(3.0),  # Second sleep call
            mock.call(3.0),  # Third sleep call
        ]
        self.assertEqual(4, self.session.request.call_count)
        mock_sleep.assert_has_calls(expected_sleep_calls, any_order=False)
        self.assertEqual(500, response.status)

    @patch('asyncio.sleep', return_value=None)
    async def test_http_call_infinite_retries(self, _):
        retry_count = 0
        max_test_retries = 6  # Simulates "indefinite" retries for test purposes

        # Function to simulate request behavior
        async def mock_request(*args, **kwargs):
            nonlocal retry_count
            retry_count += 1
            if retry_count < max_test_retries:
                return MagicMock(status=500)  # Simulate failure
            else:
                return MagicMock(status=200)  # Simulate success to stop retrying

        self.session.request = mock_request

        policy = RetryPolicy(max_attempts=-1, retryable_http_status_codes=[500])
        response = await policy.make_http_call(self.session, self.req)

        # Assert that the retry logic was executed the expected number of times
        self.assertEqual(response.status, 200)
        self.assertEqual(retry_count, max_test_retries)
