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

from typing import Any
import unittest
from datetime import timedelta

from dapr.actor.runtime._timer_data import ActorTimerData


class ActorTimerDataTests(unittest.TestCase):
    def test_timer_data(self):
        def my_callback(input: Any):
            print(input)

        timer = ActorTimerData(
            'timer_name',
            my_callback,
            'called',
            timedelta(seconds=2),
            timedelta(seconds=1),
            timedelta(seconds=3),
        )
        self.assertEqual('timer_name', timer.timer_name)
        self.assertEqual('my_callback', timer.callback)
        self.assertEqual('called', timer.state)
        self.assertEqual(timedelta(seconds=2), timer.due_time)
        self.assertEqual(timedelta(seconds=1), timer.period)
        self.assertEqual(timedelta(seconds=3), timer.ttl)

    def test_as_dict(self):
        def my_callback(input: Any):
            print(input)

        timer = ActorTimerData(
            'timer_name',
            my_callback,
            'called',
            timedelta(seconds=1),
            timedelta(seconds=1),
            timedelta(seconds=1),
        )
        expected = {
            'callback': 'my_callback',
            'data': 'called',
            'dueTime': timedelta(seconds=1),
            'period': timedelta(seconds=1),
            'ttl': timedelta(seconds=1),
        }
        self.assertDictEqual(expected, timer.as_dict())
