# -*- coding: utf-8 -*-

"""
Copyright (c) Microsoft Corporation.
Licensed under the MIT License.
"""

import unittest
from unittest.mock import patch

from dapr.clients.grpc.client import DaprClient
from dapr.proto import common_v1
from .fake_dapr_server import FakeDaprSidecar
from dapr.conf import settings
from dapr.clients.grpc._helpers import to_bytes


class DaprGrpcClientTests(unittest.TestCase):
    server_port = 8080

    def setUp(self):
        self._fake_dapr_server = FakeDaprSidecar()
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
            id='targetId',
            method='bytes',
            data=b'haha',
            content_type="text/plain",
            metadata=(
                ('key1', 'value1'),
                ('key2', 'value2'),
            ),
        )

        self.assertEqual(b'haha', resp.data)
        self.assertEqual("text/plain", resp.content_type)
        self.assertEqual(3, len(resp.headers))
        self.assertEqual(['value1'], resp.headers['hkey1'])

    def test_invoke_service_proto_data(self):
        dapr = DaprClient(f'localhost:{self.server_port}')
        req = common_v1.StateItem(key='test')
        resp = dapr.invoke_service(
            id='targetId',
            method='proto',
            data=req,
            metadata=(
                ('key1', 'value1'),
                ('key2', 'value2'),
            ),
        )

        self.assertEqual(3, len(resp.headers))
        self.assertEqual(['value1'], resp.headers['hkey1'])
        self.assertTrue(resp.is_proto())

        # unpack to new protobuf object
        new_resp = common_v1.StateItem()
        resp.unpack(new_resp)
        self.assertEqual('test', new_resp.key)

    def test_invoke_binding_bytes_data(self):
        dapr = DaprClient(f'localhost:{self.server_port}')
        resp = dapr.invoke_binding(
            name='binding',
            operation='create',
            data=b'haha',
            binding_metadata={
                'key1': 'value1',
                'key2': 'value2',
            },
        )

        self.assertEqual(b'haha', resp.data)
        self.assertEqual({'key1': 'value1', 'key2': 'value2'}, resp.binding_metadata)
        self.assertEqual(2, len(resp.headers))
        self.assertEqual(['value1'], resp.headers['hkey1'])

    def test_invoke_binding_no_metadata(self):
        dapr = DaprClient(f'localhost:{self.server_port}')
        resp = dapr.invoke_binding(
            name='binding',
            operation='create',
            data=b'haha',
        )

        self.assertEqual(b'haha', resp.data)
        self.assertEqual({}, resp.binding_metadata)
        self.assertEqual(0, len(resp.headers))

    def test_invoke_binding_no_create(self):
        dapr = DaprClient(f'localhost:{self.server_port}')
        resp = dapr.invoke_binding(
            name='binding',
            operation='delete',
            data=b'haha',
        )

        self.assertEqual(b'INVALID', resp.data)
        self.assertEqual({}, resp.binding_metadata)
        self.assertEqual(0, len(resp.headers))

    def test_publish_event(self):
        dapr = DaprClient(f'localhost:{self.server_port}')
        resp = dapr.publish_event(
            topic='example',
            data=b'haha',
        )

        self.assertEqual(2, len(resp.headers))
        self.assertEqual(['haha'], resp.headers['hdata'])

    def test_publish_error(self):
        dapr = DaprClient(f'localhost:{self.server_port}')
        with self.assertRaisesRegex(ValueError, "invalid type for data <class 'int'>"):
            dapr.publish_event(
                topic='example',
                data=111,
            )

    @patch.object(settings, 'DAPR_API_TOKEN', 'test-token')
    def test_dapr_api_token_insertion(self):
        dapr = DaprClient(f'localhost:{self.server_port}')
        resp = dapr.invoke_service(
            id='targetId',
            method='bytes',
            data=b'haha',
            content_type="text/plain",
            metadata=(
                ('key1', 'value1'),
                ('key2', 'value2'),
            ),
        )

        self.assertEqual(b'haha', resp.data)
        self.assertEqual("text/plain", resp.content_type)
        self.assertEqual(4, len(resp.headers))
        self.assertEqual(['value1'], resp.headers['hkey1'])
        self.assertEqual(['test-token'], resp.headers['hdapr-api-token'])

    def test_get_save_state(self):
        dapr = DaprClient(f'localhost:{self.server_port}')
        key = "key_1"
        value = "value_1"
        resp = dapr.save_state(
            store_name="statestore",
            key=key,
            value=value
        )
        resp = dapr.get_state(store_name="statestore", key=key)

        self.assertEqual(to_bytes(value), resp.data)

    def test_get_secret(self):
        dapr = DaprClient(f'localhost:{self.server_port}')
        key1 = 'key_1'
        resp = dapr.get_secret(
            store_name='store_1',
            key=key1,
            metadata=(
                ('key1', 'value1'),
                ('key2', 'value2'),
            ),
        )

        self.assertEqual(1, len(resp.headers))
        self.assertEqual([key1], resp.headers['keyh'])
        self.assertEqual({key1: "val"}, resp._secret)

    def test_get_secret_metadata_absent(self):
        dapr = DaprClient(f'localhost:{self.server_port}')
        key1 = 'key_1'
        resp = dapr.get_secret(
            store_name='store_1',
            key=key1,
        )

        self.assertEqual(1, len(resp.headers))
        self.assertEqual([key1], resp.headers['keyh'])
        self.assertEqual({key1: "val"}, resp._secret)


if __name__ == '__main__':
    unittest.main()
