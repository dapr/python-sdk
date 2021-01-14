# -*- coding: utf-8 -*-

"""
Copyright (c) Microsoft Corporation.
Licensed under the MIT License.
"""

from typing import Any
import unittest
from datetime import timedelta

from dapr.actor.runtime._timer_data import ActorTimerData


class ActorTimerDataTests(unittest.TestCase):
    def test_timer_data(self):
        def my_callback(input: Any):
            print(input)
        timer = ActorTimerData(
            'timer_name', my_callback, 'called',
            timedelta(seconds=2), timedelta(seconds=1))
        self.assertEqual('timer_name', timer.timer_name)
        self.assertEqual('my_callback', timer.callback)
        self.assertEqual('called', timer.state)
        self.assertEqual(timedelta(seconds=2), timer.due_time)
        self.assertEqual(timedelta(seconds=1), timer.period)

    def test_as_dict(self):
        def my_callback(input: Any):
            print(input)
        timer = ActorTimerData(
            'timer_name', my_callback, 'called',
            timedelta(seconds=1), timedelta(seconds=1))
        expected = {
            'callback': 'my_callback',
            'data': 'called',
            'dueTime': timedelta(seconds=1),
            'period': timedelta(seconds=1),
        }
        self.assertDictEqual(expected, timer.as_dict())
