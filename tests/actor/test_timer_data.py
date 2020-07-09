# -*- coding: utf-8 -*-

"""
Copyright (c) Microsoft Corporation.
Licensed under the MIT License.
"""

import unittest
from datetime import timedelta

from dapr.actor.runtime._timer_data import ActorTimerData


class ActorTimerDataTests(unittest.TestCase):
    def test_timer_data(self):
        def test_callback(obj):
            self.assertEqual('called', obj)
        timer = ActorTimerData(
            'timer_name', test_callback, 'called',
            timedelta(seconds=1), timedelta(seconds=1))
        self.assertEqual(test_callback, timer.callback)
        timer.callback('called')

    def test_as_dict(self):
        def test_callback(obj):
            self.assertEqual('called', obj)
        timer = ActorTimerData(
            'timer_name', test_callback, 'called',
            timedelta(seconds=1), timedelta(seconds=1))
        expected = {
            'dueTime': timedelta(seconds=1),
            'period': timedelta(seconds=1),
        }
        self.assertDictEqual(expected, timer.as_dict())
