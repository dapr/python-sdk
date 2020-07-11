# -*- coding: utf-8 -*-

"""
Copyright (c) Microsoft Corporation.
Licensed under the MIT License.
"""

import unittest

from dapr.clients.grpc._request import InvokeServiceRequestData, InvokeBindingRequestData
from dapr.proto import common_v1


class InvokeServiceRequestDataTests(unittest.TestCase):
    def test_bytes_data(self):
        # act
        data = InvokeServiceRequestData(data=b'hello dapr')

        # arrange
        self.assertIsNotNone(data.data)
        self.assertEqual('', data.data.type_url)
        self.assertEqual(b'hello dapr', data.data.value)
        self.assertEqual('application/json; charset=utf-8', data.content_type)

    def test_proto_message_data(self):
        # arrange
        fake_req = common_v1.InvokeRequest(method="test")

        # act
        data = InvokeServiceRequestData(data=fake_req)

        # assert
        self.assertIsNotNone(data.data)
        self.assertEqual(
            'type.googleapis.com/dapr.proto.common.v1.InvokeRequest',
            data.data.type_url)
        self.assertIsNotNone(data.data.value)
        self.assertIsNone(data.content_type)

    def test_invalid_data(self):
        with self.assertRaises(ValueError):
            data = InvokeServiceRequestData(data=123)
            self.assertIsNone(data, 'This should not be reached.')


class InvokeBindingRequestDataTests(unittest.TestCase):
    def test_bytes_data(self):
        # act
        data = InvokeBindingRequestData(data=b'hello dapr')

        # arrange
        self.assertEqual(b'hello dapr', data.data)
        self.assertEqual({}, data.metadata)

    def test_str_data(self):
        # act
        data = InvokeBindingRequestData(data='hello dapr')

        # arrange
        self.assertEqual(b'hello dapr', data.data)
        self.assertEqual({}, data.metadata)

    def test_non_empty_metadata(self):
        # act
        data = InvokeBindingRequestData(data='hello dapr', metadata=(('ttlInSeconds', '1000'), ))

        # arrange
        self.assertEqual(b'hello dapr', data.data)
        self.assertEqual({'ttlInSeconds': '1000'}, data.metadata)


if __name__ == '__main__':
    unittest.main()
