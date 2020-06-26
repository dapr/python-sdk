# -*- coding: utf-8 -*-

"""
Copyright (c) Microsoft Corporation.
Licensed under the MIT License.
"""

import unittest
import grpc

from google.protobuf.any_pb2 import Any as GrpcAny
from datetime import timedelta
from dapr.clients.grpc.dapr_client import (
    MetadataDict,
    MetadataTuple,
    DaprResponse,
    InvokeServiceRequestData,
    InvokeServiceResponse,
    DaprClient,
)
from dapr.proto import common_v1, api_service_v1
from .fake_dapr_server import FakeDaprServer


class DaprClientTests(unittest.TestCase):
    server_port = 8080
    def setUp(self):
        self._fake_dapr_server = FakeDaprServer()
        self._fake_dapr_server.start(self.server_port)

    def tearDown(self):
        self._fake_dapr_server.stop()
    
    def test_http_extension(self):
        dapr = DaprClient(f'localhost:{self.server_port}')

        # Test POST verb without querystring
        ext = dapr._get_http_extension('POST')
        self.assertEqual(common_v1.HTTPExtension.Verb.POST, ext.verb)

        # Test Non-supported http verb
        with self.assertRaises(ValueError):
            ext = dapr._get_http_extension('')
        
        # Test POST verb with querystring
        qs = (
            ('query1', 'string1'),
            ('query2', 'string2'),
        )
        ext = dapr._get_http_extension('POST', qs)

        self.assertEqual(common_v1.HTTPExtension.Verb.POST, ext.verb)
        for key, val in qs:
            self.assertEqual(val, ext.querystring[key])

    def test_invoke_service_bytes_data(self):
        dapr = DaprClient(f'localhost:{self.server_port}')
        resp = dapr.invoke_service(
            'targetId',
            'bytes',
            InvokeServiceRequestData(b'haha', "text/plain"),
            metadata=(
                ('key1', 'value1'),
                ('key2', 'value2'),
            ),
        )

        self.assertEqual(b'haha', resp.data)
        self.assertEqual("text/plain", resp.content_type)
        self.assertEqual(3, len(resp.as_headers_dict))
        self.assertEqual(['value1'], resp.as_headers_dict['hkey1'])
        self.assertEqual(['value1'], resp.as_trailers_dict['tkey1'])

    def test_invoke_service_bytes_data(self):
        dapr = DaprClient(f'localhost:{self.server_port}')
        resp = dapr.invoke_service(
            'targetId',
            'bytes',
            InvokeServiceRequestData(b'haha', "text/plain"),
            metadata=(
                ('key1', 'value1'),
                ('key2', 'value2'),
            ),
        )

        self.assertEqual(b'haha', resp.data)
        self.assertEqual("text/plain", resp.content_type)
        self.assertEqual(3, len(resp.as_headers_dict))
        self.assertEqual(['value1'], resp.as_headers_dict['hkey1'])
        self.assertEqual(['value1'], resp.as_trailers_dict['tkey1'])

    def test_invoke_service_proto_data(self):
        dapr = DaprClient(f'localhost:{self.server_port}')
        req = common_v1.StateItem(key='test')
        resp = dapr.invoke_service(
            'targetId',
            'proto',
            InvokeServiceRequestData(req),
            metadata=(
                ('key1', 'value1'),
                ('key2', 'value2'),
            ),
        )

        self.assertEqual(3, len(resp.as_headers_dict))
        self.assertEqual(['value1'], resp.as_headers_dict['hkey1'])
        self.assertEqual(['value1'], resp.as_trailers_dict['tkey1'])
        self.assertTrue(resp.is_proto())

        # unpack to new protobuf object
        new_resp = common_v1.StateItem()
        resp.unpack(new_resp)
        self.assertEqual('test', new_resp.key)


if __name__ == '__main__':
    unittest.main()
