# -*- coding: utf-8 -*-

"""
Copyright (c) Microsoft Corporation.
Licensed under the MIT License.
"""

import unittest
from datetime import timedelta

from dapr.serializers.util import convert_from_dapr_duration, convert_to_dapr_duration


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

    def test_convert_invalid_duration(self):
        delta = convert_from_dapr_duration('invalid')
        self.assertEqual(delta.total_seconds(), 0.0)

    def test_convert_timedelta_to_dapr_duariton(self):
        duration = convert_to_dapr_duration(timedelta(hours=4, minutes=15, seconds=40))
        self.assertEqual(duration, '4h15m40s')


if __name__ == '__main__':
    unittest.main()
