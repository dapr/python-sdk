# -*- coding: utf-8 -*-

"""
Copyright 2023 The Dapr Authors
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

from dapr.ext.workflow.retry_policy import RetryPolicy


class RetryPolicyTests(unittest.TestCase):
    def test_allow_infinite_max_number_of_attempts(self):
        retry_policy = RetryPolicy(
            first_retry_interval=timedelta(seconds=1), max_number_of_attempts=-1
        )

        self.assertEqual(-1, retry_policy.max_number_of_attempts)

    def test_reject_invalid_max_number_of_attempts(self):
        with self.assertRaises(ValueError):
            RetryPolicy(first_retry_interval=timedelta(seconds=1), max_number_of_attempts=0)

        with self.assertRaises(ValueError):
            RetryPolicy(first_retry_interval=timedelta(seconds=1), max_number_of_attempts=-2)
