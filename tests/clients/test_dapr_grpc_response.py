# -*- coding: utf-8 -*-

"""
Copyright (c) Microsoft Corporation.
Licensed under the MIT License.
"""

import unittest

from google.protobuf.any_pb2 import Any as GrpcAny

from dapr.clients.grpc.dapr_client import (
    DaprResponse,
    InvokeServiceResponse,
)
from dapr.proto import common_v1


test_headers = (
    ('key1', 'value1'),
    ('key2', 'value2'),
    ('key3', 'value3'),
)

test_trailers = (
    ('key10', 'value10'),
    ('key11', 'value11'),
)


class DaprResponseTests(unittest.TestCase):
    def test_convert_metadata(self):
        # act
        resp = DaprResponse(test_headers, test_trailers)

        # assert
        self.assertEqual(3, len(resp.as_headers_dict))
        for k, v in test_headers:
            self.assertEqual(resp.as_headers_dict[k], [v])
        self.assertEqual(2, len(resp.as_trailers_dict))
        for k, v in test_trailers:
            self.assertEqual(resp.as_trailers_dict[k], [v])


class InvokeServiceResponseTests(unittest.TestCase):
    def test_non_protobuf_message(self):
        with self.assertRaises(ValueError):
            resp = InvokeServiceResponse(data="invalid_datatype")
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
        test_data = GrpcAny()
        test_data.Pack(fake_req)
        resp = InvokeServiceResponse(data=test_data)
        self.assertIsNotNone(resp.proto)

    def test_data(self):
        test_data = GrpcAny(value=b'hello dapr')
        resp = InvokeServiceResponse(
            data=test_data,
            content_type='application/json')
        self.assertEqual(b'hello dapr', resp.data)
        self.assertEqual('application/json', resp.content_type)

    def test_unpack(self):
        # arrange
        fake_req = common_v1.InvokeRequest(method="test")
        test_data = GrpcAny()
        test_data.Pack(fake_req)

        # act
        resp = InvokeServiceResponse(data=test_data)
        resp_proto = common_v1.InvokeRequest()
        resp.unpack(resp_proto)

        # assert
        self.assertEqual("test", resp_proto.method)


if __name__ == '__main__':
    unittest.main()
