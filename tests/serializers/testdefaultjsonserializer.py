# -*- coding: utf-8 -*-

"""
Copyright (c) Microsoft Corporation.
Licensed under the MIT License.
"""

import unittest
import datetime

from dapr.serializers.json import DefaultJSONSerializer

class DefaultJSONSerializerTests(unittest.TestCase):
    def setUp(self):
        pass

    def test_serialize(self):
        serializer = DefaultJSONSerializer()
        input_dict_obj = {
            'propertyDecimal': 10,
            'propertyStr': 'StrValue',
            'propertyDateTime': datetime.datetime(year=2020, month=1, day=1, hour=1, minute=0, second=0, microsecond=0, tzinfo=datetime.timezone.utc)
        }
        serialized = serializer.serialize(input_dict_obj)
        self.assertEqual(serialized, b'{"propertyDecimal":10,"propertyStr":"StrValue","propertyDateTime":"2020-01-01T01:00:00Z"}')

    def test_deserialize(self):
        serializer = DefaultJSONSerializer()
        payload = b'{"propertyDecimal":10,"propertyStr":"StrValue","propertyDateTime":"2020-01-01T01:00:00Z"}'

        obj = serializer.deserialize(payload)
        self.assertEqual(obj['propertyDecimal'], 10)
        self.assertEqual(obj['propertyStr'], 'StrValue')
        self.assertTrue(isinstance(obj['propertyDateTime'], datetime.datetime))
        self.assertEqual(obj['propertyDateTime'],
            datetime.datetime(year=2020, month=1, day=1, hour=1, minute=0, second=0, microsecond=0, tzinfo=datetime.timezone.utc))

if __name__ == '__main__':
    unittest.main()
