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
import json
from datetime import timedelta

from dapr.serializers.util import convert_from_dapr_duration, convert_to_dapr_duration
from dapr.serializers.json import DaprJSONDecoder


class UtilTests(unittest.TestCase):
    def setUp(self):
        pass

    def test_convert_hour_mins_secs(self):
        delta = convert_from_dapr_duration('4h15m40s')
        self.assertEqual(delta.total_seconds(), 15340.0)

    def test_convert_mins_secs(self):
        delta = convert_from_dapr_duration('15m40s')
        self.assertEqual(delta.total_seconds(), 940.0)

    def test_convert_secs(self):
        delta = convert_from_dapr_duration('40s')
        self.assertEqual(delta.total_seconds(), 40.0)

    def test_convert_millisecs(self):
        delta = convert_from_dapr_duration('123ms')
        self.assertEqual(delta.total_seconds(), 0.123)

    def test_convert_microsecs_μs(self):
        delta = convert_from_dapr_duration('123μs')
        self.assertEqual(delta.microseconds, 123)

    def test_convert_microsecs_us(self):
        delta = convert_from_dapr_duration('345us')
        self.assertEqual(delta.microseconds, 345)

    def test_convert_invalid_duration(self):
        with self.assertRaises(ValueError) as exeception_context:
            convert_from_dapr_duration('invalid')
        self.assertEqual(
            exeception_context.exception.args[0],
            "Invalid Dapr Duration format: '{}'".format('invalid'),
        )

    def test_convert_timedelta_to_dapr_duration(self):
        duration = convert_to_dapr_duration(
            timedelta(hours=4, minutes=15, seconds=40, milliseconds=123, microseconds=35)
        )
        self.assertEqual(duration, '4h15m40s123ms35μs')

    def test_convert_invalid_duration_string(self):
        TESTSTRING = '4h15m40s123ms35μshello'
        with self.assertRaises(ValueError) as exeception_context:
            convert_from_dapr_duration(TESTSTRING)
        self.assertEqual(
            exeception_context.exception.args[0],
            "Invalid Dapr Duration format: '{}'".format(TESTSTRING),
        )
        decoded = json.loads(json.dumps({'somevar': TESTSTRING}), cls=DaprJSONDecoder)
        self.assertEqual(decoded['somevar'], TESTSTRING)


if __name__ == '__main__':
    unittest.main()
