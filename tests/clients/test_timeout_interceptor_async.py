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
from unittest.mock import Mock, patch
from dapr.aio.clients.grpc.interceptors import DaprClientTimeoutInterceptorAsync
from dapr.conf import settings


class DaprClientTimeoutInterceptorAsyncTests(unittest.TestCase):
    def test_intercept_unary_unary_with_timeout(self):
        continuation = Mock()
        request = Mock()
        client_call_details = Mock()
        client_call_details.method = 'method'
        client_call_details.timeout = 10
        client_call_details.metadata = 'metadata'
        client_call_details.credentials = 'credentials'
        client_call_details.wait_for_ready = 'wait_for_ready'

        DaprClientTimeoutInterceptorAsync().intercept_unary_unary(
            continuation, client_call_details, request
        )
        continuation.assert_called_once_with(client_call_details, request)

    @patch.object(settings, 'DAPR_API_TIMEOUT_SECONDS', 7)
    def test_intercept_unary_unary_without_timeout(self):
        continuation = Mock()
        request = Mock()
        client_call_details = Mock()
        client_call_details.method = 'method'
        client_call_details.timeout = None
        client_call_details.metadata = 'metadata'
        client_call_details.credentials = 'credentials'
        client_call_details.wait_for_ready = 'wait_for_ready'

        DaprClientTimeoutInterceptorAsync().intercept_unary_unary(
            continuation, client_call_details, request
        )
        called_client_call_details = continuation.call_args[0][0]
        self.assertEqual(7, called_client_call_details.timeout)
