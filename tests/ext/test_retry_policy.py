# -*- coding: utf-8 -*-

from datetime import timedelta
import unittest

from dapr.ext.workflow.retry_policy import RetryPolicy


class RetryPolicyTests(unittest.TestCase):
    def test_defaults(self):
        policy = RetryPolicy()
        self.assertEqual(policy.first_retry_interval, timedelta(seconds=1))
        self.assertEqual(policy.max_attempts, 1)
        self.assertEqual(policy.max_number_of_attempts, 1)
        self.assertEqual(policy.backoff_coefficient, 1.0)
        self.assertEqual(policy.max_retry_interval, timedelta(seconds=60))
        self.assertIsNone(policy.retry_timeout)

    def test_max_attempts_and_deprecated_alias(self):
        p1 = RetryPolicy(max_attempts=5)
        self.assertEqual(p1.max_attempts, 5)
        self.assertEqual(p1.max_number_of_attempts, 5)

        p2 = RetryPolicy(max_number_of_attempts=3)
        self.assertEqual(p2.max_attempts, 3)
        self.assertEqual(p2.max_number_of_attempts, 3)

    def test_invalid_values_raise(self):
        with self.assertRaises(ValueError):
            RetryPolicy(max_attempts=0)
        with self.assertRaises(ValueError):
            RetryPolicy(first_retry_interval=timedelta(seconds=-1))
        with self.assertRaises(ValueError):
            RetryPolicy(backoff_coefficient=0.5)
        with self.assertRaises(ValueError):
            RetryPolicy(max_retry_interval=timedelta(seconds=-1))


if __name__ == "__main__":
    unittest.main()
