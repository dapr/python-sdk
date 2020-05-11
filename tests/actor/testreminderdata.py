# -*- coding: utf-8 -*-

"""
Copyright (c) Microsoft Corporation.
Licensed under the MIT License.
"""

import unittest
from datetime import timedelta

from dapr.actor.runtime.reminderdata import ActorReminderData


class ActorReminderTests(unittest.TestCase):
    def test_invalid_state(self):
        with self.assertRaises(ValueError):
            ActorReminderData(
                'test_reminder',
                123,
                timedelta(seconds=1),
                timedelta(seconds=1))

    def test_valid_state(self):
        # bytes type state data
        reminder = ActorReminderData(
            'test_reminder',
            b'reminder_state',
            timedelta(seconds=1),
            timedelta(seconds=1))
        self.assertEqual(b'reminder_state', reminder.state)

        # str type state data
        reminder = ActorReminderData(
            'test_reminder',
            'reminder_state',
            timedelta(seconds=1),
            timedelta(seconds=1))
        self.assertEqual(b'reminder_state', reminder.state)

    def test_as_dict(self):
        reminder = ActorReminderData(
            'test_reminder',
            b'reminder_state',
            timedelta(seconds=1),
            timedelta(seconds=1))
        expected = {
            'name': 'test_reminder',
            'dueTime': timedelta(seconds=1),
            'period': timedelta(seconds=1),
            'data': 'cmVtaW5kZXJfc3RhdGU=',
        }
        self.assertDictEqual(expected, reminder.as_dict())

    def test_from_dict(self):
        reminder = ActorReminderData.from_dict({
            'name': 'test_reminder',
            'dueTime': timedelta(seconds=1),
            'period': timedelta(seconds=1),
            'data': 'cmVtaW5kZXJfc3RhdGU=',
        })
        self.assertEqual('test_reminder', reminder.name)
        self.assertEqual(timedelta(seconds=1), reminder.due_time)
        self.assertEqual(timedelta(seconds=1), reminder.period)
        self.assertEqual(b'reminder_state', reminder.state)
