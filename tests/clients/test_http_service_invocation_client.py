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
import unittest

from .fake_http_server import FakeHttpServer
from asyncio import TimeoutError
from dapr.conf import settings
from dapr.clients import DaprClient
from dapr.clients.exceptions import DaprInternalError
from dapr.proto import common_v1
from opencensus.trace.tracer import Tracer   # type: ignore
from opencensus.trace import print_exporter, samplers


class DaprInvocationHttpClientTests(unittest.TestCase):
    def setUp(self):
        self.server = FakeHttpServer()
        self.server_port = self.server.get_port()
        self.server.start()
        settings.DAPR_HTTP_PORT = self.server_port
        settings.DAPR_API_METHOD_INVOCATION_PROTOCOL = 'http'
        self.client = DaprClient()
        self.app_id = 'fakeapp'
        self.method_name = 'fakemethod'
        self.invoke_url = f'/v1.0/invoke/{self.app_id}/method/{self.method_name}'

    def tearDown(self):
        self.server.shutdown_server()
        settings.DAPR_API_TOKEN = None
        settings.DAPR_API_METHOD_INVOCATION_PROTOCOL = 'http'

    def test_basic_invoke(self):
        self.server.set_response(b"STRING_BODY")

        response = self.client.invoke_method(self.app_id, self.method_name, "")

        self.assertEqual(b"STRING_BODY", response.data)
        self.assertEqual(self.invoke_url, self.server.request_path())

    def test_invoke_PUT_with_body(self):
        self.server.set_response(b"STRING_BODY")

        response = self.client.invoke_method(self.app_id, self.method_name, b"FOO", http_verb='PUT')

        self.assertEqual(b"STRING_BODY", response.data)
        self.assertEqual(self.invoke_url, self.server.request_path())
        self.assertEqual(b"FOO", self.server.get_request_body())

    def test_invoke_PUT_with_bytes_body(self):
        self.server.set_response(b"STRING_BODY")

        response = self.client.invoke_method(self.app_id, self.method_name, b"FOO", http_verb='PUT')

        self.assertEqual(b"STRING_BODY", response.data)
        self.assertEqual(self.invoke_url, self.server.request_path())
        self.assertEqual(b"FOO", self.server.get_request_body())

    def test_invoke_GET_with_query_params(self):
        self.server.set_response(b"STRING_BODY")
        query_params = (('key1', 'value1'),
                        ('key2', 'value2'))

        response = self.client.invoke_method(
            self.app_id,
            self.method_name,
            '',
            http_querystring=query_params)

        self.assertEqual(b"STRING_BODY", response.data)
        self.assertEqual(f"{self.invoke_url}?key1=value1&key2=value2", self.server.request_path())

    def test_invoke_GET_with_duplicate_query_params(self):
        self.server.set_response(b"STRING_BODY")
        query_params = (('key1', 'value1'),
                        ('key1', 'value2'))

        response = self.client.invoke_method(
            self.app_id,
            self.method_name,
            '',
            http_querystring=query_params)

        self.assertEqual(b"STRING_BODY", response.data)
        self.assertEqual(f"{self.invoke_url}?key1=value1&key1=value2", self.server.request_path())

    def test_invoke_PUT_with_content_type(self):
        self.server.set_response(b"STRING_BODY")

        sample_object = {'foo': ['val1', 'val2']}

        response = self.client.invoke_method(
            self.app_id,
            self.method_name,
            json.dumps(sample_object),
            content_type='application/json')

        self.assertEqual(b"STRING_BODY", response.data)
        self.assertEqual(b'{"foo": ["val1", "val2"]}', self.server.get_request_body())

    def test_invoke_method_proto_data(self):
        self.server.set_response(b"\x0a\x04resp")
        self.server.reply_header('Content-Type', 'application/x-protobuf')

        req = common_v1.StateItem(key='test')
        resp = self.client.invoke_method(
            self.app_id,
            self.method_name,
            http_verb='PUT',
            data=req
        )

        self.assertEqual(b"\x0a\x04test", self.server.get_request_body())
        # unpack to new protobuf object
        new_resp = common_v1.StateItem()
        resp.unpack(new_resp)
        self.assertEqual('resp', new_resp.key)

    def test_invoke_method_metadata(self):
        self.server.set_response(b"FOO")

        req = common_v1.StateItem(key='test')
        resp = self.client.invoke_method(
            self.app_id,
            self.method_name,
            http_verb='PUT',
            data=req,
            metadata=(('header1', 'value1'),
                      ('header2', 'value2'))
        )

        request_headers = self.server.get_request_headers()

        self.assertEqual(b'FOO', resp.data)

        self.assertEqual('value1', request_headers['header1'])
        self.assertEqual('value2', request_headers['header2'])

    def test_invoke_method_protobuf_response_with_suffix(self):
        self.server.set_response(b"\x0a\x04resp")
        self.server.reply_header('Content-Type', 'application/x-protobuf; gzip')

        req = common_v1.StateItem(key='test')
        resp = self.client.invoke_method(
            self.app_id,
            self.method_name,
            http_verb='PUT',
            data=req,
            metadata=(('header1', 'value1'),
                      ('header2', 'value2'))
        )
        self.assertEqual(b"\x0a\x04test", self.server.get_request_body())
        # unpack to new protobuf object
        new_resp = common_v1.StateItem()
        resp.unpack(new_resp)
        self.assertEqual('resp', new_resp.key)

    def test_invoke_method_protobuf_response_case_insensitive(self):
        self.server.set_response(b"\x0a\x04resp")
        self.server.reply_header('Content-Type', 'apPlicaTion/x-protobuf; gzip')

        req = common_v1.StateItem(key='test')
        resp = self.client.invoke_method(
            self.app_id,
            self.method_name,
            http_verb='PUT',
            data=req,
            metadata=(('header1', 'value1'),
                      ('header2', 'value2'))
        )

        self.assertEqual(b"\x0a\x04test", self.server.get_request_body())
        # unpack to new protobuf object
        new_resp = common_v1.StateItem()
        resp.unpack(new_resp)
        self.assertEqual('resp', new_resp.key)

    def test_invoke_method_error_returned(self):
        error_response = b'{"errorCode":"ERR_DIRECT_INVOKE","message":"Something bad happend"}'
        self.server.set_response(error_response, 500)

        expected_msg = "('Something bad happend', 'ERR_DIRECT_INVOKE')"

        with self.assertRaises(DaprInternalError) as ctx:
            self.client.invoke_method(
                self.app_id,
                self.method_name,
                http_verb='PUT',
                data='FOO',
            )
        self.assertEqual(expected_msg, str(ctx.exception))

    def test_invoke_method_non_dapr_error(self):
        error_response = b'UNPARSABLE_ERROR'
        self.server.set_response(error_response, 500)

        expected_msg = "Unknown Dapr Error. HTTP status code: 500"

        with self.assertRaises(DaprInternalError) as ctx:
            self.client.invoke_method(
                self.app_id,
                self.method_name,
                http_verb='PUT',
                data='FOO',
            )
        self.assertEqual(expected_msg, str(ctx.exception))

    def test_generic_client_unknown_protocol(self):
        settings.DAPR_API_METHOD_INVOCATION_PROTOCOL = 'unknown'

        expected_msg = "Unknown value for DAPR_API_METHOD_INVOCATION_PROTOCOL: UNKNOWN"

        with self.assertRaises(DaprInternalError) as ctx:
            client = DaprClient()

        self.assertEqual(expected_msg, str(ctx.exception))

        settings.DAPR_API_METHOD_INVOCATION_PROTOCOL = 'grpc'
        client = DaprClient()

        self.assertIsNotNone(client)

        settings.DAPR_API_METHOD_INVOCATION_PROTOCOL = 'http'
        client = DaprClient()

        self.assertIsNotNone(client)

    def test_invoke_method_with_api_token(self):
        self.server.set_response(b"FOO")
        settings.DAPR_API_TOKEN = 'c29saSBkZW8gZ2xvcmlhCg=='

        req = common_v1.StateItem(key='test')
        resp = self.client.invoke_method(
            self.app_id,
            self.method_name,
            http_verb='PUT',
            data=req,
        )

        request_headers = self.server.get_request_headers()

        self.assertEqual('c29saSBkZW8gZ2xvcmlhCg==', request_headers['dapr-api-token'])
        self.assertEqual(b'FOO', resp.data)

    def test_invoke_method_with_tracer(self):
        tracer = Tracer(sampler=samplers.AlwaysOnSampler(), exporter=print_exporter.PrintExporter())

        self.client = DaprClient(
            headers_callback=lambda: tracer.propagator.to_headers(tracer.span_context))
        self.server.set_response(b"FOO")

        with tracer.span(name="test"):
            req = common_v1.StateItem(key='test')
            resp = self.client.invoke_method(
                self.app_id,
                self.method_name,
                http_verb='PUT',
                data=req,
            )

        request_headers = self.server.get_request_headers()

        self.assertIn('Traceparent', request_headers)
        self.assertEqual(b'FOO', resp.data)

    def test_timeout_exception_thrown_when_timeout_reached(self):
        new_client = DaprClient(http_timeout_seconds=1)
        self.server.set_server_delay(1.5)
        with self.assertRaises(TimeoutError):
            new_client.invoke_method(self.app_id, self.method_name, "")

    def test_global_timeout_setting_is_honored(self):
        previous_timeout = settings.DAPR_HTTP_TIMEOUT_SECONDS
        settings.DAPR_HTTP_TIMEOUT_SECONDS = 1
        new_client = DaprClient()
        self.server.set_server_delay(1.5)
        with self.assertRaises(TimeoutError):
            new_client.invoke_method(self.app_id, self.method_name, "")

        settings.DAPR_HTTP_TIMEOUT_SECONDS = previous_timeout
