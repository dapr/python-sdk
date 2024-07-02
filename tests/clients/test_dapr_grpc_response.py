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

from google.protobuf.any_pb2 import Any as GrpcAny

from dapr.clients.grpc._response import (
    DaprResponse,
    InvokeMethodResponse,
    BindingResponse,
    StateResponse,
    BulkStateItem,
    EncryptResponse,
    DecryptResponse,
)

from dapr.proto import api_v1, common_v1


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


class InvokeMethodResponseTests(unittest.TestCase):
    def test_non_protobuf_message(self):
        with self.assertRaises(ValueError):
            resp = InvokeMethodResponse(data=123)
            self.assertIsNone(resp, 'This should not be reached.')

    def test_is_proto_for_non_protobuf(self):
        test_data = GrpcAny(value=b'hello dapr')
        resp = InvokeMethodResponse(data=test_data, content_type='application/json')
        self.assertFalse(resp.is_proto())

    def test_is_proto_for_protobuf(self):
        fake_req = common_v1.InvokeRequest(method='test')
        test_data = GrpcAny()
        test_data.Pack(fake_req)
        resp = InvokeMethodResponse(data=test_data)
        self.assertTrue(resp.is_proto())

    def test_proto(self):
        fake_req = common_v1.InvokeRequest(method='test')
        resp = InvokeMethodResponse(data=fake_req)
        self.assertIsNotNone(resp.proto)

    def test_data(self):
        test_data = GrpcAny(value=b'hello dapr')
        resp = InvokeMethodResponse(data=test_data, content_type='application/json')
        self.assertEqual(b'hello dapr', resp.data)
        self.assertEqual('hello dapr', resp.text())
        self.assertEqual('application/json', resp.content_type)

    def test_json_data(self):
        resp = InvokeMethodResponse(data=b'{ "status": "ok" }', content_type='application/json')
        self.assertEqual({'status': 'ok'}, resp.json())

    def test_unpack(self):
        # arrange
        fake_req = common_v1.InvokeRequest(method='test')

        # act
        resp = InvokeMethodResponse(data=fake_req)
        resp_proto = common_v1.InvokeRequest()
        resp.unpack(resp_proto)

        # assert
        self.assertEqual('test', resp_proto.method)


class InvokeBindingResponseTests(unittest.TestCase):
    def test_bytes_message(self):
        resp = BindingResponse(data=b'data', binding_metadata={})
        self.assertEqual({}, resp.binding_metadata)
        self.assertEqual(b'data', resp.data)
        self.assertEqual('data', resp.text())

    def test_json_data(self):
        resp = BindingResponse(data=b'{"status": "ok"}', binding_metadata={})
        self.assertEqual({'status': 'ok'}, resp.json())

    def test_metadata(self):
        resp = BindingResponse(data=b'data', binding_metadata={'status': 'ok'})
        self.assertEqual({'status': 'ok'}, resp.binding_metadata)
        self.assertEqual(b'data', resp.data)
        self.assertEqual('data', resp.text())


class StateResponseTests(unittest.TestCase):
    def test_data(self):
        resp = StateResponse(data=b'hello dapr')
        self.assertEqual('hello dapr', resp.text())
        self.assertEqual(b'hello dapr', resp.data)

    def test_json_data(self):
        resp = StateResponse(data=b'{"status": "ok"}')
        self.assertEqual({'status': 'ok'}, resp.json())


class BulkStateItemTests(unittest.TestCase):
    def test_data(self):
        item = BulkStateItem(key='item1', data=b'{ "status": "ok" }')
        self.assertEqual({'status': 'ok'}, item.json())


class CryptoResponseTests(unittest.TestCase):
    def response_stream(self):
        stream1 = common_v1.StreamPayload(data=b'hello', seq=0)
        stream2 = common_v1.StreamPayload(data=b' dapr', seq=1)
        for strm in (stream1, stream2):
            yield api_v1.EncryptResponse(payload=strm)

    def test_encrypt_response_read_bytes(self):
        resp = EncryptResponse(stream=self.response_stream())
        self.assertEqual(resp.read(5), b'hello')
        self.assertEqual(resp.read(5), b' dapr')

    def test_encrypt_response_read_all(self):
        resp = EncryptResponse(stream=self.response_stream())
        self.assertEqual(resp.read(), b'hello dapr')

    def test_decrypt_response_read_bytes(self):
        resp = DecryptResponse(stream=self.response_stream())
        self.assertEqual(resp.read(5), b'hello')
        self.assertEqual(resp.read(5), b' dapr')

    def test_decrypt_response_read_all(self):
        resp = DecryptResponse(stream=self.response_stream())
        self.assertEqual(resp.read(), b'hello dapr')


if __name__ == '__main__':
    unittest.main()
