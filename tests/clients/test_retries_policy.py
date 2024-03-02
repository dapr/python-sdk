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

from grpc import StatusCode

from dapr.clients.retry import RetryPolicy


class RetryPolicyGrpcTests(unittest.TestCase):
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
