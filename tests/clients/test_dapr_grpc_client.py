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
import asyncio

from unittest.mock import patch
from dapr.clients.grpc.client import DaprGrpcClient
from dapr.clients import DaprClient
from dapr.proto import common_v1
from .fake_dapr_server import FakeDaprSidecar
from dapr.conf import settings
from dapr.clients.grpc._helpers import to_bytes
from dapr.clients.grpc._request import TransactionalStateOperation
from dapr.clients.grpc._state import StateOptions, Consistency, Concurrency, StateItem
from dapr.clients.grpc._response import (
    ConfigurationItem,
    ConfigurationResponse,
    ConfigurationWatcher,
    UnlockResponseStatus,
    WorkflowRuntimeStatus,
)


class DaprGrpcClientTests(unittest.TestCase):
    server_port = 8080
    scheme = ""

    def setUp(self):
        self._fake_dapr_server = FakeDaprSidecar()
        self._fake_dapr_server.start(self.server_port)

    def tearDown(self):
        self._fake_dapr_server.stop()

    def test_http_extension(self):
        dapr = DaprGrpcClient(f"{self.scheme}localhost:{self.server_port}")

        # Test POST verb without querystring
        ext = dapr._get_http_extension("POST")
        self.assertEqual(common_v1.HTTPExtension.Verb.POST, ext.verb)

        # Test Non-supported http verb
        with self.assertRaises(ValueError):
            ext = dapr._get_http_extension("")

        # Test POST verb with querystring
        qs = (
            ("query1", "string1"),
            ("query2", "string2"),
            ("query1", "string 3"),
        )
        ext = dapr._get_http_extension("POST", qs)

        self.assertEqual(common_v1.HTTPExtension.Verb.POST, ext.verb)
        self.assertEqual("query1=string1&query2=string2&query1=string+3", ext.querystring)

    def test_invoke_method_bytes_data(self):
        dapr = DaprGrpcClient(f"{self.scheme}localhost:{self.server_port}")
        resp = dapr.invoke_method(
            app_id="targetId",
            method_name="bytes",
            data=b"haha",
            content_type="text/plain",
            metadata=(
                ("key1", "value1"),
                ("key2", "value2"),
            ),
            http_verb="PUT",
        )

        self.assertEqual(b"haha", resp.data)
        self.assertEqual("text/plain", resp.content_type)
        self.assertEqual(3, len(resp.headers))
        self.assertEqual(["value1"], resp.headers["hkey1"])

    def test_invoke_method_no_data(self):
        dapr = DaprGrpcClient(f"{self.scheme}localhost:{self.server_port}")
        resp = dapr.invoke_method(
            app_id="targetId",
            method_name="bytes",
            content_type="text/plain",
            metadata=(
                ("key1", "value1"),
                ("key2", "value2"),
            ),
            http_verb="PUT",
        )

        self.assertEqual(b"", resp.data)
        self.assertEqual("text/plain", resp.content_type)
        self.assertEqual(3, len(resp.headers))
        self.assertEqual(["value1"], resp.headers["hkey1"])

    def test_invoke_method_async(self):
        dapr = DaprClient(f"{self.scheme}localhost:{self.server_port}")
        dapr.invocation_client = None  # force to use grpc client

        with self.assertRaises(NotImplementedError):
            loop = asyncio.new_event_loop()
            loop.run_until_complete(
                dapr.invoke_method_async(
                    app_id="targetId",
                    method_name="bytes",
                    data=b"haha",
                    content_type="text/plain",
                    metadata=(
                        ("key1", "value1"),
                        ("key2", "value2"),
                    ),
                    http_verb="PUT",
                )
            )

    def test_invoke_method_proto_data(self):
        dapr = DaprGrpcClient(f"{self.scheme}localhost:{self.server_port}")
        req = common_v1.StateItem(key="test")
        resp = dapr.invoke_method(
            app_id="targetId",
            method_name="proto",
            data=req,
            metadata=(
                ("key1", "value1"),
                ("key2", "value2"),
            ),
        )

        self.assertEqual(3, len(resp.headers))
        self.assertEqual(["value1"], resp.headers["hkey1"])
        self.assertTrue(resp.is_proto())

        # unpack to new protobuf object
        new_resp = common_v1.StateItem()
        resp.unpack(new_resp)
        self.assertEqual("test", new_resp.key)

    def test_invoke_binding_bytes_data(self):
        dapr = DaprGrpcClient(f"{self.scheme}localhost:{self.server_port}")
        resp = dapr.invoke_binding(
            binding_name="binding",
            operation="create",
            data=b"haha",
            binding_metadata={
                "key1": "value1",
                "key2": "value2",
            },
        )

        self.assertEqual(b"haha", resp.data)
        self.assertEqual({"key1": "value1", "key2": "value2"}, resp.binding_metadata)
        self.assertEqual(2, len(resp.headers))
        self.assertEqual(["value1"], resp.headers["hkey1"])

    def test_invoke_binding_no_metadata(self):
        dapr = DaprGrpcClient(f"{self.scheme}localhost:{self.server_port}")
        resp = dapr.invoke_binding(
            binding_name="binding",
            operation="create",
            data=b"haha",
        )

        self.assertEqual(b"haha", resp.data)
        self.assertEqual({}, resp.binding_metadata)
        self.assertEqual(0, len(resp.headers))

    def test_invoke_binding_no_data(self):
        dapr = DaprGrpcClient(f"{self.scheme}localhost:{self.server_port}")
        resp = dapr.invoke_binding(
            binding_name="binding",
            operation="create",
        )

        self.assertEqual(b"", resp.data)
        self.assertEqual({}, resp.binding_metadata)
        self.assertEqual(0, len(resp.headers))

    def test_invoke_binding_no_create(self):
        dapr = DaprGrpcClient(f"{self.scheme}localhost:{self.server_port}")
        resp = dapr.invoke_binding(
            binding_name="binding",
            operation="delete",
            data=b"haha",
        )

        self.assertEqual(b"INVALID", resp.data)
        self.assertEqual({}, resp.binding_metadata)
        self.assertEqual(0, len(resp.headers))

    def test_publish_event(self):
        dapr = DaprGrpcClient(f"{self.scheme}localhost:{self.server_port}")
        resp = dapr.publish_event(pubsub_name="pubsub", topic_name="example", data=b"haha")

        self.assertEqual(2, len(resp.headers))
        self.assertEqual(["haha"], resp.headers["hdata"])

    def test_publish_event_with_content_type(self):
        dapr = DaprGrpcClient(f"{self.scheme}localhost:{self.server_port}")
        resp = dapr.publish_event(
            pubsub_name="pubsub",
            topic_name="example",
            data=b'{"foo": "bar"}',
            data_content_type="application/json",
        )

        self.assertEqual(3, len(resp.headers))
        self.assertEqual(['{"foo": "bar"}'], resp.headers["hdata"])
        self.assertEqual(["application/json"], resp.headers["data_content_type"])

    def test_publish_event_with_metadata(self):
        dapr = DaprGrpcClient(f"{self.scheme}localhost:{self.server_port}")
        resp = dapr.publish_event(
            pubsub_name="pubsub",
            topic_name="example",
            data=b'{"foo": "bar"}',
            publish_metadata={"ttlInSeconds": "100", "rawPayload": "false"},
        )

        print(resp.headers)
        self.assertEqual(['{"foo": "bar"}'], resp.headers["hdata"])
        self.assertEqual(["false"], resp.headers["metadata_raw_payload"])
        self.assertEqual(["100"], resp.headers["metadata_ttl_in_seconds"])

    def test_publish_error(self):
        dapr = DaprGrpcClient(f"{self.scheme}localhost:{self.server_port}")
        with self.assertRaisesRegex(ValueError, "invalid type for data <class 'int'>"):
            dapr.publish_event(
                pubsub_name="pubsub",
                topic_name="example",
                data=111,
            )

    @patch.object(settings, "DAPR_API_TOKEN", "test-token")
    def test_dapr_api_token_insertion(self):
        dapr = DaprGrpcClient(f"{self.scheme}localhost:{self.server_port}")
        resp = dapr.invoke_method(
            app_id="targetId",
            method_name="bytes",
            data=b"haha",
            content_type="text/plain",
            metadata=(
                ("key1", "value1"),
                ("key2", "value2"),
            ),
        )

        self.assertEqual(b"haha", resp.data)
        self.assertEqual("text/plain", resp.content_type)
        self.assertEqual(4, len(resp.headers))
        self.assertEqual(["value1"], resp.headers["hkey1"])
        self.assertEqual(["test-token"], resp.headers["hdapr-api-token"])

    def test_get_save_delete_state(self):
        dapr = DaprGrpcClient(f"{self.scheme}localhost:{self.server_port}")
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
            etag="fake_etag",
            options=options,
            state_metadata={"capitalize": "1"},
        )

        resp = dapr.get_state(store_name="statestore", key=key)
        self.assertEqual(resp.data, to_bytes(value.capitalize()))
        self.assertEqual(resp.etag, "fake_etag")

        resp = dapr.get_state(store_name="statestore", key=key, state_metadata={"upper": "1"})
        self.assertEqual(resp.data, to_bytes(value.upper()))
        self.assertEqual(resp.etag, "fake_etag")

        resp = dapr.get_state(store_name="statestore", key="NotValidKey")
        self.assertEqual(resp.data, b"")
        self.assertEqual(resp.etag, "")

        dapr.delete_state(store_name="statestore", key=key)
        resp = dapr.get_state(store_name="statestore", key=key)
        self.assertEqual(resp.data, b"")
        self.assertEqual(resp.etag, "")

        with self.assertRaises(Exception) as context:
            dapr.delete_state(store_name="statestore", key=key, state_metadata={"must_delete": "1"})
        print(context.exception)
        self.assertTrue("delete failed" in str(context.exception))

    def test_get_save_state_etag_none(self):
        dapr = DaprGrpcClient(f"{self.scheme}localhost:{self.server_port}")

        value = "test"
        no_etag_key = "no_etag"
        empty_etag_key = "empty_etag"
        dapr.save_state(
            store_name="statestore",
            key=no_etag_key,
            value=value,
        )

        dapr.save_state(store_name="statestore", key=empty_etag_key, value=value, etag="")

        resp = dapr.get_state(store_name="statestore", key=no_etag_key)
        self.assertEqual(resp.data, to_bytes(value))
        self.assertEqual(resp.etag, "ETAG_WAS_NONE")

        resp = dapr.get_state(store_name="statestore", key=empty_etag_key)
        self.assertEqual(resp.data, to_bytes(value))
        self.assertEqual(resp.etag, "")

    def test_transaction_then_get_states(self):
        dapr = DaprGrpcClient(f"{self.scheme}localhost:{self.server_port}")

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
            transactional_metadata={"metakey": "metavalue"},
        )

        resp = dapr.get_bulk_state(store_name="statestore", keys=[key, another_key])
        self.assertEqual(resp.items[0].key, key)
        self.assertEqual(resp.items[0].data, to_bytes(value))
        self.assertEqual(resp.items[0].etag, "foo")
        self.assertEqual(resp.items[1].key, another_key)
        self.assertEqual(resp.items[1].data, to_bytes(another_value))
        self.assertEqual(resp.items[1].etag, "ETAG_WAS_NONE")

        resp = dapr.get_bulk_state(
            store_name="statestore", keys=[key, another_key], states_metadata={"upper": "1"}
        )
        self.assertEqual(resp.items[0].key, key)
        self.assertEqual(resp.items[0].data, to_bytes(value.upper()))
        self.assertEqual(resp.items[1].key, another_key)
        self.assertEqual(resp.items[1].data, to_bytes(another_value.upper()))

    def test_save_then_get_states(self):
        dapr = DaprGrpcClient(f"{self.scheme}localhost:{self.server_port}")

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
            metadata=(("metakey", "metavalue"),),
        )

        resp = dapr.get_bulk_state(store_name="statestore", keys=[key, another_key])
        self.assertEqual(resp.items[0].key, key)
        self.assertEqual(resp.items[0].etag, "ETAG_WAS_NONE")
        self.assertEqual(resp.items[0].data, to_bytes(value.capitalize()))
        self.assertEqual(resp.items[1].key, another_key)
        self.assertEqual(resp.items[1].data, to_bytes(another_value))
        self.assertEqual(resp.items[1].etag, "1")

        resp = dapr.get_bulk_state(
            store_name="statestore", keys=[key, another_key], states_metadata={"upper": "1"}
        )
        self.assertEqual(resp.items[0].key, key)
        self.assertEqual(resp.items[0].etag, "ETAG_WAS_NONE")
        self.assertEqual(resp.items[0].data, to_bytes(value.upper()))
        self.assertEqual(resp.items[1].key, another_key)
        self.assertEqual(resp.items[1].etag, "1")
        self.assertEqual(resp.items[1].data, to_bytes(another_value.upper()))

    def test_get_secret(self):
        dapr = DaprGrpcClient(f"{self.scheme}localhost:{self.server_port}")
        key1 = "key_1"
        resp = dapr.get_secret(
            store_name="store_1",
            key=key1,
            metadata=(
                ("key1", "value1"),
                ("key2", "value2"),
            ),
        )

        self.assertEqual(1, len(resp.headers))
        self.assertEqual([key1], resp.headers["keyh"])
        self.assertEqual({key1: "val"}, resp._secret)

    def test_get_secret_metadata_absent(self):
        dapr = DaprGrpcClient(f"{self.scheme}localhost:{self.server_port}")
        key1 = "key_1"
        resp = dapr.get_secret(
            store_name="store_1",
            key=key1,
        )

        self.assertEqual(1, len(resp.headers))
        self.assertEqual([key1], resp.headers["keyh"])
        self.assertEqual({key1: "val"}, resp._secret)

    def test_get_bulk_secret(self):
        dapr = DaprGrpcClient(f"{self.scheme}localhost:{self.server_port}")
        resp = dapr.get_bulk_secret(
            store_name="store_1",
            metadata=(
                ("key1", "value1"),
                ("key2", "value2"),
            ),
        )

        self.assertEqual(1, len(resp.headers))
        self.assertEqual(["bulk"], resp.headers["keyh"])
        self.assertEqual({"keya": {"keyb": "val"}}, resp._secrets)

    def test_get_bulk_secret_metadata_absent(self):
        dapr = DaprGrpcClient(f"{self.scheme}localhost:{self.server_port}")
        resp = dapr.get_bulk_secret(store_name="store_1")

        self.assertEqual(1, len(resp.headers))
        self.assertEqual(["bulk"], resp.headers["keyh"])
        self.assertEqual({"keya": {"keyb": "val"}}, resp._secrets)

    def test_get_configuration(self):
        dapr = DaprGrpcClient(f"{self.scheme}localhost:{self.server_port}")
        keys = ["k", "k1"]
        value = "value"
        version = "1.5.0"
        metadata = {}

        resp = dapr.get_configuration(store_name="configurationstore", keys=keys)
        self.assertEqual(len(resp.items), len(keys))
        self.assertIn(keys[0], resp.items)
        item = resp.items[keys[0]]
        self.assertEqual(item.value, value)
        self.assertEqual(item.version, version)
        self.assertEqual(item.metadata, metadata)

        resp = dapr.get_configuration(
            store_name="configurationstore", keys=keys, config_metadata=metadata
        )
        self.assertEqual(len(resp.items), len(keys))
        self.assertIn(keys[0], resp.items)
        item = resp.items[keys[0]]
        self.assertEqual(item.value, value)
        self.assertEqual(item.version, version)
        self.assertEqual(item.metadata, metadata)

    def test_subscribe_configuration(self):
        dapr = DaprGrpcClient(f"{self.scheme}localhost:{self.server_port}")

        def mock_watch(self, stub, store_name, keys, handler, config_metadata):
            handler(
                "id",
                ConfigurationResponse(
                    items={"k": ConfigurationItem(value="test", version="1.7.0")}
                ),
            )
            return "id"

        def handler(id: str, resp: ConfigurationResponse):
            self.assertEqual(resp.items["k"].value, "test")
            self.assertEqual(resp.items["k"].version, "1.7.0")

        with patch.object(ConfigurationWatcher, "watch_configuration", mock_watch):
            dapr.subscribe_configuration(
                store_name="configurationstore", keys=["k"], handler=handler
            )

    def test_unsubscribe_configuration(self):
        dapr = DaprGrpcClient(f"{self.scheme}localhost:{self.server_port}")
        res = dapr.unsubscribe_configuration(store_name="configurationstore", id="k")
        self.assertTrue(res)

    def test_query_state(self):
        dapr = DaprGrpcClient(f"{self.scheme}localhost:{self.server_port}")

        resp = dapr.query_state(
            store_name="statestore",
            query=json.dumps({"filter": {}, "page": {"limit": 2}}),
        )
        self.assertEqual(resp.results[0].key, "1")
        self.assertEqual(len(resp.results), 2)

        resp = dapr.query_state(
            store_name="statestore",
            query=json.dumps({"filter": {}, "page": {"limit": 3, "token": "3"}}),
        )
        self.assertEqual(resp.results[0].key, "3")
        self.assertEqual(len(resp.results), 3)

    def test_shutdown(self):
        dapr = DaprGrpcClient(f"{self.scheme}localhost:{self.server_port}")
        dapr.shutdown()
        self.assertTrue(self._fake_dapr_server.shutdown_received)

    def test_wait_ok(self):
        dapr = DaprGrpcClient(f"{self.scheme}localhost:{self.server_port}")
        dapr.wait(0.1)

    def test_wait_timeout(self):
        # First, pick an unused port
        port = 0
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(("", 0))
            port = s.getsockname()[1]
        dapr = DaprGrpcClient(f"localhost:{port}")
        with self.assertRaises(Exception) as context:
            dapr.wait(0.1)
        self.assertTrue("Connection refused" in str(context.exception))

    def test_lock_acquire_success(self):
        dapr = DaprGrpcClient(f"{self.scheme}localhost:{self.server_port}")
        # Lock parameters
        store_name = "lockstore"
        resource_id = str(uuid.uuid4())
        lock_owner = str(uuid.uuid4())
        expiry_in_seconds = 60

        success = dapr.try_lock(store_name, resource_id, lock_owner, expiry_in_seconds)
        self.assertTrue(success)
        unlock_response = dapr.unlock(store_name, resource_id, lock_owner)
        self.assertEqual(UnlockResponseStatus.success, unlock_response.status)

    def test_lock_release_twice_fails(self):
        dapr = DaprGrpcClient(f"{self.scheme}localhost:{self.server_port}")
        # Lock parameters
        store_name = "lockstore"
        resource_id = str(uuid.uuid4())
        lock_owner = str(uuid.uuid4())
        expiry_in_seconds = 60

        success = dapr.try_lock(store_name, resource_id, lock_owner, expiry_in_seconds)
        self.assertTrue(success)
        unlock_response = dapr.unlock(store_name, resource_id, lock_owner)
        self.assertEqual(UnlockResponseStatus.success, unlock_response.status)
        # If client tries again it will discover the lock is gone
        unlock_response = dapr.unlock(store_name, resource_id, lock_owner)
        self.assertEqual(UnlockResponseStatus.lock_does_not_exist, unlock_response.status)

    def test_lock_conflict(self):
        dapr = DaprGrpcClient(f"{self.scheme}localhost:{self.server_port}")
        # Lock parameters
        store_name = "lockstore"
        resource_id = str(uuid.uuid4())
        first_client_id = str(uuid.uuid4())
        second_client_id = str(uuid.uuid4())
        expiry_in_seconds = 60

        # First client succeeds
        success = dapr.try_lock(store_name, resource_id, first_client_id, expiry_in_seconds)
        self.assertTrue(success)
        # Second client tries and fails - resource already acquired
        success = dapr.try_lock(store_name, resource_id, second_client_id, expiry_in_seconds)
        self.assertFalse(success)
        # Second client is a sneaky fellow and tries to release a lock it doesn't own
        unlock_response = dapr.unlock(store_name, resource_id, second_client_id)
        self.assertEqual(UnlockResponseStatus.lock_belongs_to_others, unlock_response.status)
        # First client can stil return the lock as rightful owner
        unlock_response = dapr.unlock(store_name, resource_id, first_client_id)
        self.assertEqual(UnlockResponseStatus.success, unlock_response.status)

    def test_lock_not_previously_acquired(self):
        dapr = DaprGrpcClient(f"{self.scheme}localhost:{self.server_port}")
        unlock_response = dapr.unlock(
            store_name="lockstore", resource_id=str(uuid.uuid4()), lock_owner=str(uuid.uuid4())
        )
        self.assertEqual(UnlockResponseStatus.lock_does_not_exist, unlock_response.status)

    def test_lock_release_twice_fails_with_context_manager(self):
        dapr = DaprGrpcClient(f"{self.scheme}localhost:{self.server_port}")
        # Lock parameters
        store_name = "lockstore"
        resource_id = str(uuid.uuid4())
        first_client_id = str(uuid.uuid4())
        second_client_id = str(uuid.uuid4())
        expiry = 60

        with dapr.try_lock(store_name, resource_id, first_client_id, expiry) as first_lock:
            self.assertTrue(first_lock.success)
            # If another client tries to acquire the same lock it will fail
            with dapr.try_lock(store_name, resource_id, second_client_id, expiry) as second_lock:
                self.assertFalse(second_lock.success)
        # At this point lock was auto-released
        # If client tries again it will discover the lock is gone
        unlock_response = dapr.unlock(store_name, resource_id, first_client_id)
        self.assertEqual(UnlockResponseStatus.lock_does_not_exist, unlock_response.status)

    def test_lock_are_not_reentrant(self):
        dapr = DaprGrpcClient(f"{self.scheme}localhost:{self.server_port}")
        # Lock parameters
        store_name = "lockstore"
        resource_id = str(uuid.uuid4())
        client_id = str(uuid.uuid4())
        expiry_in_s = 60

        with dapr.try_lock(store_name, resource_id, client_id, expiry_in_s) as first_attempt:
            self.assertTrue(first_attempt.success)
            # If the same client tries to acquire the same lock again it will fail.
            with dapr.try_lock(store_name, resource_id, client_id, expiry_in_s) as second_attempt:
                self.assertFalse(second_attempt.success)

    def test_lock_input_validation(self):
        dapr = DaprGrpcClient(f"{self.scheme}localhost:{self.server_port}")
        # Sane parameters
        store_name = "lockstore"
        resource_id = str(uuid.uuid4())
        client_id = str(uuid.uuid4())
        expiry_in_s = 60
        # Invalid inputs for string arguments
        for invalid_input in [None, "", "   "]:
            # store_name
            with self.assertRaises(ValueError):
                with dapr.try_lock(invalid_input, resource_id, client_id, expiry_in_s) as res:
                    self.assertTrue(res.success)
            # resource_id
            with self.assertRaises(ValueError):
                with dapr.try_lock(store_name, invalid_input, client_id, expiry_in_s) as res:
                    self.assertTrue(res.success)
            # client_id
            with self.assertRaises(ValueError):
                with dapr.try_lock(store_name, resource_id, invalid_input, expiry_in_s) as res:
                    self.assertTrue(res.success)
        # Invalid inputs for expiry_in_s
        for invalid_input in [None, -1, 0]:
            with self.assertRaises(ValueError):
                with dapr.try_lock(store_name, resource_id, client_id, invalid_input) as res:
                    self.assertTrue(res.success)

    def test_unlock_input_validation(self):
        dapr = DaprGrpcClient(f"{self.scheme}localhost:{self.server_port}")
        # Sane parameters
        store_name = "lockstore"
        resource_id = str(uuid.uuid4())
        client_id = str(uuid.uuid4())
        # Invalid inputs for string arguments
        for invalid_input in [None, "", "   "]:
            # store_name
            with self.assertRaises(ValueError):
                dapr.unlock(invalid_input, resource_id, client_id)
            # resource_id
            with self.assertRaises(ValueError):
                dapr.unlock(store_name, invalid_input, client_id)
            # client_id
            with self.assertRaises(ValueError):
                dapr.unlock(store_name, resource_id, invalid_input)

    #
    # Tests for workflow
    #

    def test_workflow(self):
        dapr = DaprGrpcClient(f"{self.scheme}localhost:{self.server_port}")
        # Sane parameters
        workflow_name = "test_workflow"
        event_name = "eventName"
        instance_id = str(uuid.uuid4())
        workflow_component = "dapr"
        input = "paperclips"
        event_data = "cars"

        # Start the workflow
        start_response = dapr.start_workflow(
            instance_id=instance_id,
            workflow_name=workflow_name,
            workflow_component=workflow_component,
            input=input,
            workflow_options=None,
        )
        self.assertEqual(instance_id, start_response.instance_id)

        # Get info on the workflow to check that it is running
        get_response = dapr.get_workflow(
            instance_id=instance_id, workflow_component=workflow_component
        )
        self.assertEqual(WorkflowRuntimeStatus.RUNNING.value, get_response.runtime_status)

        # Pause the workflow
        dapr.pause_workflow(instance_id, workflow_component)

        # Get info on the workflow to check that it is paused
        get_response = dapr.get_workflow(instance_id, workflow_component)
        self.assertEqual(WorkflowRuntimeStatus.SUSPENDED.value, get_response.runtime_status)

        # Resume the workflow
        dapr.resume_workflow(instance_id, workflow_component)

        # Get info on the workflow to check that it is resumed
        get_response = dapr.get_workflow(instance_id, workflow_component)
        self.assertEqual(WorkflowRuntimeStatus.RUNNING.value, get_response.runtime_status)

        # Raise an event on the workflow.
        dapr.raise_workflow_event(instance_id, workflow_component, event_name, event_data)
        get_response = dapr.get_workflow(instance_id, workflow_component)
        self.assertEqual(event_data, get_response.properties[instance_id].strip('""'))

        # Terminate the workflow
        dapr.terminate_workflow(instance_id, workflow_component)

        # Get info on the workflow to check that it is terminated
        get_response = dapr.get_workflow(instance_id, workflow_component)
        self.assertEqual(WorkflowRuntimeStatus.TERMINATED.value, get_response.runtime_status)

        # Purge the workflow
        dapr.purge_workflow(instance_id, workflow_component)

        # Get information on the workflow to ensure that it has been purged
        try:
            get_response = dapr.get_workflow(instance_id, workflow_component)
        except Exception as err:
            self.assertIn("Workflow instance does not exist", str(err))

    #
    # Tests for Metadata API
    #

    def test_get_metadata(self):
        with DaprGrpcClient(f"{self.scheme}localhost:{self.server_port}") as dapr:
            response = dapr.get_metadata()

            self.assertIsNotNone(response)

            self.assertEqual(response.application_id, "myapp")

            actors = response.active_actors_count
            self.assertIsNotNone(actors)
            self.assertTrue(len(actors) > 0)
            for actorType, count in actors.items():
                # Assert both are non-null and non-empty/zero
                self.assertTrue(actorType)
                self.assertTrue(count)

            self.assertIsNotNone(response.registered_components)
            self.assertTrue(len(response.registered_components) > 0)
            components = {c.name: c for c in response.registered_components}
            # common tests for all components
            for c in components.values():
                self.assertTrue(c.name)
                self.assertTrue(c.type)
                self.assertIsNotNone(c.version)
                self.assertIsNotNone(c.capabilities)
            self.assertTrue("ETAG" in components["statestore"].capabilities)

            self.assertIsNotNone(response.extended_metadata)

    def test_set_metadata(self):
        metadata_key = "test_set_metadata_attempt"
        with DaprGrpcClient(f"{self.scheme}localhost:{self.server_port}") as dapr:
            for metadata_value in [str(i) for i in range(10)]:
                dapr.set_metadata(attributeName=metadata_key, attributeValue=metadata_value)
                response = dapr.get_metadata()
                self.assertIsNotNone(response)
                self.assertIsNotNone(response.extended_metadata)
                self.assertEqual(response.extended_metadata[metadata_key], metadata_value)
            # Empty string and blank strings should be accepted just fine
            # by this API
            for metadata_value in ["", "    "]:
                dapr.set_metadata(attributeName=metadata_key, attributeValue=metadata_value)
                response = dapr.get_metadata()
                self.assertIsNotNone(response)
                self.assertIsNotNone(response.extended_metadata)
                self.assertEqual(response.extended_metadata[metadata_key], metadata_value)

    def test_set_metadata_input_validation(self):
        dapr = DaprGrpcClient(f"{self.scheme}localhost:{self.server_port}")
        valid_attr_name = "attribute name"
        valid_attr_value = "attribute value"
        # Invalid inputs for string arguments
        with DaprGrpcClient(f"{self.scheme}localhost:{self.server_port}") as dapr:
            for invalid_attr_name in [None, "", "   "]:
                with self.assertRaises(ValueError):
                    dapr.set_metadata(invalid_attr_name, valid_attr_value)
            # We are less strict with attribute values - we just cannot accept None
            for invalid_attr_value in [None]:
                with self.assertRaises(ValueError):
                    dapr.set_metadata(valid_attr_name, invalid_attr_value)


if __name__ == "__main__":
    unittest.main()
