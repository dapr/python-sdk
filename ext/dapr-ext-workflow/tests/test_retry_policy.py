# -*- coding: utf-8 -*-

"""
Copyright 2026 The Dapr Authors
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
from datetime import timedelta

from dapr.ext.workflow import RetryPolicy


class RetryPolicyConstructionTests(unittest.TestCase):
    def test_constructs_with_legacy_max_number_of_attempts(self):
        policy = RetryPolicy(
            first_retry_interval=timedelta(seconds=1),
            max_number_of_attempts=5,
        )

        self.assertEqual(policy.first_retry_interval, timedelta(seconds=1))
        self.assertEqual(policy.max_number_of_attempts, 5)
        self.assertEqual(policy.max_attempts, 5)
        self.assertEqual(policy.backoff_coefficient, 1.0)
        self.assertIsNone(policy.max_retry_interval)
        self.assertIsNone(policy.retry_timeout)

    def test_constructs_with_new_max_attempts(self):
        policy = RetryPolicy(
            first_retry_interval=timedelta(seconds=2),
            max_attempts=3,
            backoff_coefficient=2.0,
            max_retry_interval=timedelta(seconds=10),
            retry_timeout=timedelta(minutes=5),
        )

        self.assertEqual(policy.first_retry_interval, timedelta(seconds=2))
        self.assertEqual(policy.max_attempts, 3)
        self.assertEqual(policy.max_number_of_attempts, 3)
        self.assertEqual(policy.backoff_coefficient, 2.0)
        self.assertEqual(policy.max_retry_interval, timedelta(seconds=10))
        self.assertEqual(policy.retry_timeout, timedelta(minutes=5))

    def test_exposes_underlying_durabletask_object(self):
        policy = RetryPolicy(
            first_retry_interval=timedelta(seconds=1),
            max_attempts=2,
        )

        underlying = policy.obj
        self.assertEqual(underlying._max_number_of_attempts, 2)
        self.assertEqual(underlying._first_retry_interval, timedelta(seconds=1))


class RetryPolicyAttemptsResolutionTests(unittest.TestCase):
    def test_rejects_when_both_attempts_fields_supplied(self):
        with self.assertRaises(ValueError) as ctx:
            RetryPolicy(
                first_retry_interval=timedelta(seconds=1),
                max_attempts=3,
                max_number_of_attempts=3,
            )

        self.assertIn('only one of max_attempts', str(ctx.exception))

    def test_rejects_when_neither_attempts_field_supplied(self):
        with self.assertRaises(ValueError) as ctx:
            RetryPolicy(first_retry_interval=timedelta(seconds=1))

        self.assertIn('max_attempts is required', str(ctx.exception))


class RetryPolicyValidationTests(unittest.TestCase):
    def test_rejects_negative_first_retry_interval(self):
        with self.assertRaisesRegex(ValueError, 'first_retry_interval'):
            RetryPolicy(
                first_retry_interval=timedelta(seconds=-1),
                max_attempts=2,
            )

    def test_rejects_max_attempts_below_one(self):
        with self.assertRaisesRegex(ValueError, 'max_attempts'):
            RetryPolicy(
                first_retry_interval=timedelta(seconds=1),
                max_attempts=0,
            )

    def test_rejects_backoff_coefficient_below_one(self):
        with self.assertRaisesRegex(ValueError, 'backoff_coefficient'):
            RetryPolicy(
                first_retry_interval=timedelta(seconds=1),
                max_attempts=2,
                backoff_coefficient=0.5,
            )

    def test_rejects_negative_max_retry_interval(self):
        with self.assertRaisesRegex(ValueError, 'max_retry_interval'):
            RetryPolicy(
                first_retry_interval=timedelta(seconds=1),
                max_attempts=2,
                max_retry_interval=timedelta(seconds=-1),
            )

    def test_rejects_negative_retry_timeout(self):
        with self.assertRaisesRegex(ValueError, 'retry_timeout'):
            RetryPolicy(
                first_retry_interval=timedelta(seconds=1),
                max_attempts=2,
                retry_timeout=timedelta(seconds=-1),
            )

    def test_allows_backoff_coefficient_none(self):
        policy = RetryPolicy(
            first_retry_interval=timedelta(seconds=1),
            max_attempts=2,
            backoff_coefficient=None,
        )

        self.assertIsNone(policy.backoff_coefficient)


if __name__ == '__main__':
    unittest.main()
