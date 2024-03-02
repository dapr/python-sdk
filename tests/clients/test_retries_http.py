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
from unittest.mock import patch, MagicMock, AsyncMock

from dapr.clients.http.client import DaprHttpClient
from dapr.clients.retry import RetryPolicy
from dapr.serializers import DefaultJSONSerializer


class RetryPolicyHttpTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        # Setup your test environment and mocks here
        self.session = MagicMock()
        self.session.request = AsyncMock()

        self.serializer = (DefaultJSONSerializer(),)
        self.client = DaprHttpClient(message_serializer=self.serializer)

        # Example request
        self.req = {
            'method': 'GET',
            'url': 'http://example.com',
            'data': None,
            'headers': None,
            'sslcontext': None,
            'params': None,
        }

    async def test_run_with_success(self):
        # Mock the request to succeed on the first try
        self.session.request.return_value.status = 200

        response = await self.client.retry_call(self.session, self.req)

        self.session.request.assert_called_once()
        self.assertEqual(200, response.status)

    async def test_success_run_with_no_retry(self):
        self.session.request.return_value.status = 200

        client = DaprHttpClient(
            message_serializer=self.serializer, retry_policy=RetryPolicy(max_attempts=0)
        )
        response = await client.retry_call(self.session, self.req)

        self.session.request.assert_called_once()
        self.assertEqual(200, response.status)

    async def test_fail_run_with_no_retry(self):
        self.session.request.return_value.status = 408

        client = DaprHttpClient(
            message_serializer=self.serializer, retry_policy=RetryPolicy(max_attempts=0)
        )
        response = await client.retry_call(self.session, self.req)

        self.session.request.assert_called_once()
        self.assertEqual(408, response.status)

    @patch('asyncio.sleep', return_value=None)
    async def test_retry_eventually_succeeds(self, _):
        # Mock the request to fail twice then succeed
        self.session.request.side_effect = [
            MagicMock(status=500),  # First attempt fails
            MagicMock(status=502),  # Second attempt fails
            MagicMock(status=200),  # Third attempt succeeds
        ]
        client = DaprHttpClient(
            message_serializer=self.serializer, retry_policy=RetryPolicy(max_attempts=3)
        )

        response = await client.retry_call(self.session, self.req)

        self.assertEqual(3, self.session.request.call_count)
        self.assertEqual(200, response.status)

    @patch('asyncio.sleep', return_value=None)
    async def test_retry_eventually_fails(self, _):
        self.session.request.return_value.status = 408

        client = DaprHttpClient(
            message_serializer=self.serializer, retry_policy=RetryPolicy(max_attempts=3)
        )

        response = await client.retry_call(self.session, self.req)

        self.assertEqual(3, self.session.request.call_count)
        self.assertEqual(408, response.status)

    @patch('asyncio.sleep', return_value=None)
    async def test_retry_fails_with_a_different_code(self, _):
        # Mock the request to fail twice then succeed
        self.session.request.return_value.status = 501

        client = DaprHttpClient(
            message_serializer=self.serializer,
            retry_policy=RetryPolicy(max_attempts=3, retryable_http_status_codes=[500]),
        )

        response = await client.retry_call(self.session, self.req)

        self.session.request.assert_called_once()
        self.assertEqual(response.status, 501)

    @patch('asyncio.sleep', return_value=None)
    async def test_retries_exhausted(self, _):
        # Mock the request to fail three times
        self.session.request.return_value = MagicMock(status=500)

        client = DaprHttpClient(
            message_serializer=self.serializer,
            retry_policy=RetryPolicy(max_attempts=3, retryable_http_status_codes=[500]),
        )

        response = await client.retry_call(self.session, self.req)

        self.assertEqual(3, self.session.request.call_count)
        self.assertEqual(500, response.status)

    @patch('asyncio.sleep', return_value=None)
    async def test_max_backoff(self, mock_sleep):
        self.session.request.return_value.status = 500

        policy = RetryPolicy(max_attempts=4, initial_backoff=2, backoff_multiplier=2, max_backoff=3)
        client = DaprHttpClient(message_serializer=self.serializer, retry_policy=policy)

        response = await client.retry_call(self.session, self.req)

        expected_sleep_calls = [
            mock.call(2.0),  # First sleep call
            mock.call(3.0),  # Second sleep call
            mock.call(3.0),  # Third sleep call
        ]
        self.assertEqual(4, self.session.request.call_count)
        mock_sleep.assert_has_calls(expected_sleep_calls, any_order=False)
        self.assertEqual(500, response.status)

    @patch('asyncio.sleep', return_value=None)
    async def test_infinite_retries(self, _):
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
        client = DaprHttpClient(message_serializer=self.serializer, retry_policy=policy)

        response = await client.retry_call(self.session, self.req)

        # Assert that the retry logic was executed the expected number of times
        self.assertEqual(response.status, 200)
        self.assertEqual(retry_count, max_test_retries)
