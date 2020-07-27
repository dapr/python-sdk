# -*- coding: utf-8 -*-

"""
Copyright (c) Microsoft Corporation.
Licensed under the MIT License.
"""

import unittest

from dapr.clients.grpc._request import InvokeServiceRequest, BindingRequest
from dapr.proto import common_v1


class InvokeServiceRequestTests(unittest.TestCase):
    def test_bytes_data(self):
        # act
        req = InvokeServiceRequest(data=b'hello dapr')

        # arrange
        self.assertEqual(b'hello dapr', req.data)
        self.assertEqual('application/json; charset=utf-8', req.content_type)

    def test_proto_message_data(self):
        # arrange
        fake_req = common_v1.InvokeRequest(method="test")

        # act
        req = InvokeServiceRequest(data=fake_req)

        # assert
        self.assertIsNotNone(req.proto)
        self.assertEqual(
            'type.googleapis.com/dapr.proto.common.v1.InvokeRequest',
            req.proto.type_url)
        self.assertIsNotNone(req.proto.value)
        self.assertIsNone(req.content_type)

    def test_invalid_data(self):
        with self.assertRaises(ValueError):
            data = InvokeServiceRequest(data=123)
            self.assertIsNone(data, 'This should not be reached.')


class InvokeBindingRequestDataTests(unittest.TestCase):
    def test_bytes_data(self):
        # act
        data = BindingRequest(data=b'hello dapr')

        # arrange
        self.assertEqual(b'hello dapr', data.data)
        self.assertEqual({}, data.metadata)

    def test_str_data(self):
        # act
        data = BindingRequest(data='hello dapr')

        # arrange
        self.assertEqual(b'hello dapr', data.data)
        self.assertEqual({}, data.metadata)

    def test_non_empty_metadata(self):
        # act
        data = BindingRequest(data='hello dapr', binding_metadata={'ttlInSeconds': '1000'})

        # arrange
        self.assertEqual(b'hello dapr', data.data)
        self.assertEqual({'ttlInSeconds': '1000'}, data.binding_metadata)


if __name__ == '__main__':
    unittest.main()
