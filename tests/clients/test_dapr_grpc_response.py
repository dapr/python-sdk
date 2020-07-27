# -*- coding: utf-8 -*-

"""
Copyright (c) Microsoft Corporation.
Licensed under the MIT License.
"""

import unittest

from google.protobuf.any_pb2 import Any as GrpcAny

from dapr.clients.grpc._response import DaprResponse, InvokeServiceResponse, BindingResponse
from dapr.proto import common_v1


class DaprResponseTests(unittest.TestCase):
    test_headers = (
        ('key1', 'value1'),
        ('key2', 'value2'),
        ('key3', 'value3'),
    )

    def test_convert_metadata(self):
        # act
        resp = DaprResponse(self.test_headers)

        # assert
        self.assertEqual(3, len(resp.headers))
        for k, v in self.test_headers:
            self.assertEqual(resp.headers[k], [v])


class InvokeServiceResponseTests(unittest.TestCase):
    def test_non_protobuf_message(self):
        with self.assertRaises(ValueError):
            resp = InvokeServiceResponse(data=123)
            self.assertIsNone(resp, 'This should not be reached.')

    def test_is_proto_for_non_protobuf(self):
        test_data = GrpcAny(value=b'hello dapr')
        resp = InvokeServiceResponse(
            data=test_data,
            content_type='application/json')
        self.assertFalse(resp.is_proto())

    def test_is_proto_for_protobuf(self):
        fake_req = common_v1.InvokeRequest(method="test")
        test_data = GrpcAny()
        test_data.Pack(fake_req)
        resp = InvokeServiceResponse(data=test_data)
        self.assertTrue(resp.is_proto())

    def test_proto(self):
        fake_req = common_v1.InvokeRequest(method="test")
        resp = InvokeServiceResponse(data=fake_req)
        self.assertIsNotNone(resp.proto)

    def test_data(self):
        test_data = GrpcAny(value=b'hello dapr')
        resp = InvokeServiceResponse(
            data=test_data,
            content_type='application/json')
        self.assertEqual(b'hello dapr', resp.data)
        self.assertEqual('hello dapr', resp.text())
        self.assertEqual('application/json', resp.content_type)

    def test_unpack(self):
        # arrange
        fake_req = common_v1.InvokeRequest(method="test")

        # act
        resp = InvokeServiceResponse(data=fake_req)
        resp_proto = common_v1.InvokeRequest()
        resp.unpack(resp_proto)

        # assert
        self.assertEqual("test", resp_proto.method)


class InvokeBindingResponseTests(unittest.TestCase):
    def test_bytes_message(self):
        resp = BindingResponse(data=b'data', binding_metadata={})
        self.assertEqual({}, resp.binding_metadata)
        self.assertEqual(b'data', resp.data)
        self.assertEqual('data', resp.text())

    def test_metadata(self):
        resp = BindingResponse(data=b'data', binding_metadata={'status': 'ok'})
        self.assertEqual({'status': 'ok'}, resp.binding_metadata)
        self.assertEqual(b'data', resp.data)
        self.assertEqual('data', resp.text())


if __name__ == '__main__':
    unittest.main()
