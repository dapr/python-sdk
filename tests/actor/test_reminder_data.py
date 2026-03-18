# -*- coding: utf-8 -*-

"""
Copyright 2021 The Dapr Authors
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

from dapr.actor.runtime._reminder_data import ActorReminderData
from dapr.actor.runtime.failure_policy import ActorReminderFailurePolicy


class ActorReminderTests(unittest.TestCase):
    def test_invalid_state(self):
        with self.assertRaises(ValueError):
            ActorReminderData(
                'test_reminder',
                123,  # int type
                timedelta(seconds=1),
                timedelta(seconds=2),
                timedelta(seconds=3),
            )
            ActorReminderData(
                'test_reminder',
                'reminder_state',  # string type
                timedelta(seconds=2),
                timedelta(seconds=1),
                timedelta(seconds=3),
            )

    def test_valid_state(self):
        # bytes type state data
        reminder = ActorReminderData(
            'test_reminder',
            b'reminder_state',
            timedelta(seconds=1),
            timedelta(seconds=2),
            timedelta(seconds=3),
        )
        self.assertEqual(b'reminder_state', reminder.state)

    def test_as_dict(self):
        reminder = ActorReminderData(
            'test_reminder',
            b'reminder_state',
            timedelta(seconds=1),
            timedelta(seconds=2),
            timedelta(seconds=3),
        )
        expected = {
            'reminderName': 'test_reminder',
            'dueTime': timedelta(seconds=1),
            'period': timedelta(seconds=2),
            'ttl': timedelta(seconds=3),
            'data': 'cmVtaW5kZXJfc3RhdGU=',
        }
        self.assertDictEqual(expected, reminder.as_dict())

    def test_from_dict(self):
        reminder = ActorReminderData.from_dict(
            'test_reminder',
            {
                'dueTime': timedelta(seconds=1),
                'period': timedelta(seconds=2),
                'ttl': timedelta(seconds=3),
                'data': 'cmVtaW5kZXJfc3RhdGU=',
            },
        )
        self.assertEqual('test_reminder', reminder.reminder_name)
        self.assertEqual(timedelta(seconds=1), reminder.due_time)
        self.assertEqual(timedelta(seconds=2), reminder.period)
        self.assertEqual(timedelta(seconds=3), reminder.ttl)
        self.assertEqual(b'reminder_state', reminder.state)

    def test_no_failure_policy(self):
        reminder = ActorReminderData(
            'test_reminder',
            b'reminder_state',
            timedelta(seconds=1),
            timedelta(seconds=2),
        )
        result = reminder.as_dict()
        self.assertNotIn('failurePolicy', result)
        self.assertIsNone(reminder.failure_policy)

    def test_drop_failure_policy_as_dict(self):
        policy = ActorReminderFailurePolicy.drop_policy()
        reminder = ActorReminderData(
            'test_reminder',
            b'reminder_state',
            timedelta(seconds=1),
            timedelta(seconds=2),
            failure_policy=policy,
        )
        result = reminder.as_dict()
        self.assertIn('failurePolicy', result)
        self.assertEqual({'drop': {}}, result['failurePolicy'])

    def test_constant_failure_policy_as_dict(self):
        policy = ActorReminderFailurePolicy.constant_policy(
            interval=timedelta(seconds=5), max_retries=3
        )
        reminder = ActorReminderData(
            'test_reminder',
            b'reminder_state',
            timedelta(seconds=1),
            timedelta(seconds=2),
            failure_policy=policy,
        )
        result = reminder.as_dict()
        self.assertIn('failurePolicy', result)
        self.assertEqual(
            {'constant': {'interval': timedelta(seconds=5), 'maxRetries': 3}},
            result['failurePolicy'],
        )

    def test_failure_policy_alongside_ttl(self):
        policy = ActorReminderFailurePolicy.drop_policy()
        reminder = ActorReminderData(
            'test_reminder',
            b'reminder_state',
            timedelta(seconds=1),
            timedelta(seconds=2),
            ttl=timedelta(seconds=60),
            failure_policy=policy,
        )
        result = reminder.as_dict()
        self.assertIn('ttl', result)
        self.assertIn('failurePolicy', result)
        self.assertEqual({'drop': {}}, result['failurePolicy'])
