# -*- coding: utf-8 -*-

"""
Copyright (c) Microsoft Corporation and Dapr Contributors.
Licensed under the MIT License.
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

    def test_convert_invalid_duration(self):
        TESTSTRING = 'invalid'
        try:
            convert_from_dapr_duration(TESTSTRING)
            self.fail('Expected ValueError')
        except ValueError as e:
            self.assertEqual(str(e), "Invalid Dapr Duration format: '{}'".format(TESTSTRING))

    def test_convert_timedelta_to_dapr_duration(self):
        duration = convert_to_dapr_duration(timedelta(hours=4, minutes=15, seconds=40))
        self.assertEqual(duration, '4h15m40s')

    def test_convert_invalid_duration_string(self):
        TESTSTRING = '4h15m40shello'
        try:
            convert_from_dapr_duration(TESTSTRING)
            self.fail('Expected ValueError')
        except ValueError as e:
            self.assertEqual(str(e), "Invalid Dapr Duration format: '{}'".format(TESTSTRING))
        decoded = json.loads(json.dumps({"somevar": TESTSTRING}), cls=DaprJSONDecoder)
        self.assertEqual(decoded['somevar'], TESTSTRING)


if __name__ == '__main__':
    unittest.main()
