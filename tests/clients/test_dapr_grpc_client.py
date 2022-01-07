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

import json
import socket
import unittest
import uuid

from unittest.mock import patch

from dapr.clients.grpc.client import DaprGrpcClient
from dapr.proto import common_v1
from .fake_dapr_server import FakeDaprSidecar
from dapr.conf import settings
from dapr.clients.grpc._helpers import to_bytes
from dapr.clients.grpc._request import TransactionalStateOperation
from dapr.clients.grpc._state import StateOptions, Consistency, Concurrency, StateItem


class DaprGrpcClientTests(unittest.TestCase):
    server_port = 8080

    def setUp(self):
        self._fake_dapr_server = FakeDaprSidecar()
        self._fake_dapr_server.start(self.server_port)

    def tearDown(self):
        self._fake_dapr_server.stop()

    def test_http_extension(self):
        dapr = DaprGrpcClient(f'localhost:{self.server_port}')

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
            ('query1', 'string 3'),
        )
        ext = dapr._get_http_extension('POST', qs)

        self.assertEqual(common_v1.HTTPExtension.Verb.POST, ext.verb)
        self.assertEqual("query1=string1&query2=string2&query1=string+3", ext.querystring)

    def test_invoke_method_bytes_data(self):
        dapr = DaprGrpcClient(f'localhost:{self.server_port}')
        resp = dapr.invoke_method(
            app_id='targetId',
            method_name='bytes',
            data=b'haha',
            content_type="text/plain",
            metadata=(
                ('key1', 'value1'),
                ('key2', 'value2'),
            ),
            http_verb='PUT',
        )

        self.assertEqual(b'haha', resp.data)
        self.assertEqual("text/plain", resp.content_type)
        self.assertEqual(3, len(resp.headers))
        self.assertEqual(['value1'], resp.headers['hkey1'])

    def test_invoke_method_proto_data(self):
        dapr = DaprGrpcClient(f'localhost:{self.server_port}')
        req = common_v1.StateItem(key='test')
        resp = dapr.invoke_method(
            app_id='targetId',
            method_name='proto',
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
        dapr = DaprGrpcClient(f'localhost:{self.server_port}')
        resp = dapr.invoke_binding(
            binding_name='binding',
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
        dapr = DaprGrpcClient(f'localhost:{self.server_port}')
        resp = dapr.invoke_binding(
            binding_name='binding',
            operation='create',
            data=b'haha',
        )

        self.assertEqual(b'haha', resp.data)
        self.assertEqual({}, resp.binding_metadata)
        self.assertEqual(0, len(resp.headers))

    def test_invoke_binding_no_create(self):
        dapr = DaprGrpcClient(f'localhost:{self.server_port}')
        resp = dapr.invoke_binding(
            binding_name='binding',
            operation='delete',
            data=b'haha',
        )

        self.assertEqual(b'INVALID', resp.data)
        self.assertEqual({}, resp.binding_metadata)
        self.assertEqual(0, len(resp.headers))

    def test_publish_event(self):
        dapr = DaprGrpcClient(f'localhost:{self.server_port}')
        resp = dapr.publish_event(
            pubsub_name='pubsub',
            topic_name='example',
            data=b'haha'
        )

        self.assertEqual(2, len(resp.headers))
        self.assertEqual(['haha'], resp.headers['hdata'])

    def test_publish_event_with_content_type(self):
        dapr = DaprGrpcClient(f'localhost:{self.server_port}')
        resp = dapr.publish_event(
            pubsub_name='pubsub',
            topic_name='example',
            data=b'{"foo": "bar"}',
            data_content_type='application/json'
        )

        self.assertEqual(3, len(resp.headers))
        self.assertEqual(['{"foo": "bar"}'], resp.headers['hdata'])
        self.assertEqual(['application/json'], resp.headers['data_content_type'])

    def test_publish_event_with_metadata(self):
        dapr = DaprGrpcClient(f'localhost:{self.server_port}')
        resp = dapr.publish_event(
            pubsub_name='pubsub',
            topic_name='example',
            data=b'{"foo": "bar"}',
            publish_metadata={'ttlInSeconds': '100', 'rawPayload': 'false'}
        )

        print(resp.headers)
        self.assertEqual(['{"foo": "bar"}'], resp.headers['hdata'])
        self.assertEqual(['false'], resp.headers['metadata_raw_payload'])
        self.assertEqual(['100'], resp.headers['metadata_ttl_in_seconds'])

    def test_publish_error(self):
        dapr = DaprGrpcClient(f'localhost:{self.server_port}')
        with self.assertRaisesRegex(ValueError, "invalid type for data <class 'int'>"):
            dapr.publish_event(
                pubsub_name='pubsub',
                topic_name='example',
                data=111,
            )

    @patch.object(settings, 'DAPR_API_TOKEN', 'test-token')
    def test_dapr_api_token_insertion(self):
        dapr = DaprGrpcClient(f'localhost:{self.server_port}')
        resp = dapr.invoke_method(
            app_id='targetId',
            method_name='bytes',
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

    def test_get_save_delete_state(self):
        dapr = DaprGrpcClient(f'localhost:{self.server_port}')
        key = "key_1"
        value = "value_1"
        options = StateOptions(
            consistency=Consistency.eventual,
            concurrency=Concurrency.first_write,
        )
        dapr.save_state(
            store_name="statestore",
            key=key,
            value=value,
            etag='fake_etag',
            options=options,
            state_metadata={"capitalize": "1"}
        )

        resp = dapr.get_state(store_name="statestore", key=key)
        self.assertEqual(resp.data, to_bytes(value.capitalize()))
        self.assertEqual(resp.etag, "fake_etag")

        resp = dapr.get_state(store_name="statestore", key=key, state_metadata={"upper": "1"})
        self.assertEqual(resp.data, to_bytes(value.upper()))
        self.assertEqual(resp.etag, "fake_etag")

        resp = dapr.get_state(store_name="statestore", key="NotValidKey")
        self.assertEqual(resp.data, b'')
        self.assertEqual(resp.etag, '')

        dapr.delete_state(
            store_name="statestore",
            key=key
        )
        resp = dapr.get_state(store_name="statestore", key=key)
        self.assertEqual(resp.data, b'')
        self.assertEqual(resp.etag, '')

        with self.assertRaises(Exception) as context:
            dapr.delete_state(
                store_name="statestore",
                key=key,
                state_metadata={"must_delete": "1"})
        print(context.exception)
        self.assertTrue('delete failed' in str(context.exception))

    def test_get_save_state_etag_none(self):
        dapr = DaprGrpcClient(f'localhost:{self.server_port}')

        value = 'test'
        no_etag_key = 'no_etag'
        empty_etag_key = 'empty_etag'
        dapr.save_state(
            store_name="statestore",
            key=no_etag_key,
            value=value,
        )

        dapr.save_state(
            store_name="statestore",
            key=empty_etag_key,
            value=value,
            etag=""
        )

        resp = dapr.get_state(store_name="statestore", key=no_etag_key)
        self.assertEqual(resp.data, to_bytes(value))
        self.assertEqual(resp.etag, "ETAG_WAS_NONE")

        resp = dapr.get_state(store_name="statestore", key=empty_etag_key)
        self.assertEqual(resp.data, to_bytes(value))
        self.assertEqual(resp.etag, "")

    def test_transaction_then_get_states(self):
        dapr = DaprGrpcClient(f'localhost:{self.server_port}')

        key = str(uuid.uuid4())
        value = str(uuid.uuid4())
        another_key = str(uuid.uuid4())
        another_value = str(uuid.uuid4())

        dapr.execute_state_transaction(
            store_name="statestore",
            operations=[
                TransactionalStateOperation(key=key, data=value, etag="foo"),
                TransactionalStateOperation(key=another_key, data=another_value),
            ],
            transactional_metadata={"metakey": "metavalue"}
        )

        resp = dapr.get_bulk_state(store_name="statestore", keys=[key, another_key])
        self.assertEqual(resp.items[0].key, key)
        self.assertEqual(resp.items[0].data, to_bytes(value))
        self.assertEqual(resp.items[0].etag, "foo")
        self.assertEqual(resp.items[1].key, another_key)
        self.assertEqual(resp.items[1].data, to_bytes(another_value))
        self.assertEqual(resp.items[1].etag, "ETAG_WAS_NONE")

        resp = dapr.get_bulk_state(
            store_name="statestore",
            keys=[key, another_key],
            states_metadata={"upper": "1"})
        self.assertEqual(resp.items[0].key, key)
        self.assertEqual(resp.items[0].data, to_bytes(value.upper()))
        self.assertEqual(resp.items[1].key, another_key)
        self.assertEqual(resp.items[1].data, to_bytes(another_value.upper()))

    def test_save_then_get_states(self):
        dapr = DaprGrpcClient(f'localhost:{self.server_port}')

        key = str(uuid.uuid4())
        value = str(uuid.uuid4())
        another_key = str(uuid.uuid4())
        another_value = str(uuid.uuid4())

        dapr.save_bulk_state(
            store_name="statestore",
            states=[
                StateItem(key=key, value=value, metadata={"capitalize": "1"}),
                StateItem(key=another_key, value=another_value, etag="1"),
            ],
            metadata=(("metakey", "metavalue"),)
        )

        resp = dapr.get_bulk_state(store_name="statestore", keys=[key, another_key])
        self.assertEqual(resp.items[0].key, key)
        self.assertEqual(resp.items[0].etag, "ETAG_WAS_NONE")
        self.assertEqual(resp.items[0].data, to_bytes(value.capitalize()))
        self.assertEqual(resp.items[1].key, another_key)
        self.assertEqual(resp.items[1].data, to_bytes(another_value))
        self.assertEqual(resp.items[1].etag, "1")

        resp = dapr.get_bulk_state(
            store_name="statestore",
            keys=[key, another_key],
            states_metadata={"upper": "1"})
        self.assertEqual(resp.items[0].key, key)
        self.assertEqual(resp.items[0].etag, "ETAG_WAS_NONE")
        self.assertEqual(resp.items[0].data, to_bytes(value.upper()))
        self.assertEqual(resp.items[1].key, another_key)
        self.assertEqual(resp.items[1].etag, "1")
        self.assertEqual(resp.items[1].data, to_bytes(another_value.upper()))

    def test_get_secret(self):
        dapr = DaprGrpcClient(f'localhost:{self.server_port}')
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
        dapr = DaprGrpcClient(f'localhost:{self.server_port}')
        key1 = 'key_1'
        resp = dapr.get_secret(
            store_name='store_1',
            key=key1,
        )

        self.assertEqual(1, len(resp.headers))
        self.assertEqual([key1], resp.headers['keyh'])
        self.assertEqual({key1: "val"}, resp._secret)

    def test_get_bulk_secret(self):
        dapr = DaprGrpcClient(f'localhost:{self.server_port}')
        resp = dapr.get_bulk_secret(
            store_name='store_1',
            metadata=(
                ('key1', 'value1'),
                ('key2', 'value2'),
            ),
        )

        self.assertEqual(1, len(resp.headers))
        self.assertEqual(["bulk"], resp.headers['keyh'])
        self.assertEqual({"keya": {"keyb": "val"}}, resp._secrets)

    def test_get_bulk_secret_metadata_absent(self):
        dapr = DaprGrpcClient(f'localhost:{self.server_port}')
        resp = dapr.get_bulk_secret(store_name='store_1')

        self.assertEqual(1, len(resp.headers))
        self.assertEqual(["bulk"], resp.headers['keyh'])
        self.assertEqual({"keya": {"keyb": "val"}}, resp._secrets)

    def test_get_configuration(self):
        dapr = DaprGrpcClient(f'localhost:{self.server_port}')
        invalid_key = "N"
        key = "k"
        value = "value"
        version = "1.5.0"
        metadata = {}

        resp = dapr.get_configuration(store_name="configurationstore", keys=key)
        self.assertEqual(resp.items[0].key, key)
        self.assertEqual(resp.items[0].value, value)
        self.assertEqual(resp.items[0].version, version)
        self.assertEqual(resp.items[0].metadata, metadata)

        resp = dapr.get_configuration(
            store_name="configurationstore", keys=key, config_metadata=metadata)
        self.assertEqual(resp.items[0].key, key)
        self.assertEqual(resp.items[0].value, value)
        self.assertEqual(resp.items[0].version, version)
        self.assertEqual(resp.items[0].metadata, metadata)

        resp = dapr.get_configuration(store_name="configurationstore", keys="NotValidKey")
        self.assertEqual(resp.items[0].key, invalid_key)
        self.assertEqual(resp.items[0].value, value)
        self.assertEqual(resp.items[0].version, version)
        self.assertEqual(resp.items[0].metadata, metadata)

    def test_query_state(self):
        dapr = DaprGrpcClient(f'localhost:{self.server_port}')

        resp = dapr.query_state_alpha1(
            store_name="statestore",
            query=json.dumps({"filter": {}, "page": {"limit": 2}}),
        )
        self.assertEqual(resp.results[0].key, "1")
        self.assertEqual(len(resp.results), 2)

        resp = dapr.query_state_alpha1(
            store_name="statestore",
            query=json.dumps({"filter": {}, "page": {"limit": 3, "token": "3"}}),
        )
        self.assertEqual(resp.results[0].key, "3")
        self.assertEqual(len(resp.results), 3)

    def test_shutdown(self):
        dapr = DaprGrpcClient(f'localhost:{self.server_port}')
        dapr.shutdown()
        self.assertTrue(self._fake_dapr_server.shutdown_received)

    def test_wait_ok(self):
        dapr = DaprGrpcClient(f'localhost:{self.server_port}')
        dapr.wait(0.1)

    def test_wait_timeout(self):
        # First, pick an unused port
        port = 0
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(('', 0))
            port = s.getsockname()[1]
        dapr = DaprGrpcClient(f'localhost:{port}')
        with self.assertRaises(Exception) as context:
            dapr.wait(0.1)
        self.assertTrue('Connection refused' in str(context.exception))


if __name__ == '__main__':
    unittest.main()
