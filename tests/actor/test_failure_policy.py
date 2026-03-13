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

from dapr.actor.runtime.failure_policy import ActorReminderFailurePolicy


class ActorReminderFailurePolicyTests(unittest.TestCase):
    # --- drop_policy ---

    def test_drop_policy_factory(self):
        p = ActorReminderFailurePolicy.drop_policy()
        self.assertTrue(p.drop)
        self.assertIsNone(p.interval)
        self.assertIsNone(p.max_retries)

    def test_drop_policy_as_dict(self):
        p = ActorReminderFailurePolicy.drop_policy()
        self.assertEqual({'drop': {}}, p.as_dict())

    # --- constant_policy ---

    def test_constant_policy_interval_and_max_retries(self):
        p = ActorReminderFailurePolicy.constant_policy(interval=timedelta(seconds=5), max_retries=3)
        self.assertFalse(p.drop)
        self.assertEqual(timedelta(seconds=5), p.interval)
        self.assertEqual(3, p.max_retries)

    def test_constant_policy_as_dict_full(self):
        p = ActorReminderFailurePolicy.constant_policy(interval=timedelta(seconds=5), max_retries=3)
        self.assertEqual(
            {'constant': {'interval': timedelta(seconds=5), 'maxRetries': 3}}, p.as_dict()
        )

    def test_constant_policy_interval_only(self):
        p = ActorReminderFailurePolicy.constant_policy(interval=timedelta(seconds=10))
        self.assertEqual({'constant': {'interval': timedelta(seconds=10)}}, p.as_dict())

    def test_constant_policy_max_retries_only(self):
        p = ActorReminderFailurePolicy.constant_policy(max_retries=5)
        self.assertEqual({'constant': {'maxRetries': 5}}, p.as_dict())

    # --- validation errors ---

    def test_drop_with_interval_raises(self):
        with self.assertRaises(ValueError):
            ActorReminderFailurePolicy(drop=True, interval=timedelta(seconds=1))

    def test_drop_with_max_retries_raises(self):
        with self.assertRaises(ValueError):
            ActorReminderFailurePolicy(drop=True, max_retries=3)

    def test_drop_with_both_raises(self):
        with self.assertRaises(ValueError):
            ActorReminderFailurePolicy(drop=True, interval=timedelta(seconds=1), max_retries=3)

    def test_no_policy_specified_raises(self):
        with self.assertRaises(ValueError):
            ActorReminderFailurePolicy()

    # --- direct constructor ---

    def test_direct_drop_constructor(self):
        p = ActorReminderFailurePolicy(drop=True)
        self.assertEqual({'drop': {}}, p.as_dict())

    def test_direct_constant_constructor(self):
        p = ActorReminderFailurePolicy(interval=timedelta(seconds=2), max_retries=1)
        self.assertEqual(
            {'constant': {'interval': timedelta(seconds=2), 'maxRetries': 1}}, p.as_dict()
        )
