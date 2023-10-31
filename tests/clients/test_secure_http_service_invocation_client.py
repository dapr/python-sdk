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
import ssl
from unittest.mock import patch

from dapr.clients.http.client import DaprHttpClient
from .certs import CERTIFICATE_CHAIN_PATH
from .fake_http_server import FakeHttpServer
from dapr.conf import settings
from dapr.clients import DaprClient

from .test_http_service_invocation_client import DaprInvocationHttpClientTests


def replacement_get_ssl_context(a):
    ssl_context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    ssl_context.load_verify_locations(CERTIFICATE_CHAIN_PATH)

    return ssl_context


class DaprSecureInvocationHttpClientTests(DaprInvocationHttpClientTests):
    def setUp(self):
        DaprHttpClient.get_ssl_context = replacement_get_ssl_context

        self.server = FakeHttpServer(secure=True)
        self.server_port = self.server.get_port()
        self.server.start()
        settings.DAPR_HTTP_PORT = self.server_port
        settings.DAPR_API_METHOD_INVOCATION_PROTOCOL = 'http'
        settings.DAPR_HTTP_ENDPOINT = "https://localhost:{}".format(self.server_port)
        self.client = DaprClient()
        self.app_id = 'fakeapp'
        self.method_name = 'fakemethod'
        self.invoke_url = f'/v1.0/invoke/{self.app_id}/method/{self.method_name}'

    def tearDown(self):
        self.server.shutdown_server()
        settings.DAPR_API_TOKEN = None
        settings.DAPR_API_METHOD_INVOCATION_PROTOCOL = 'http'

    @patch.object(settings, "DAPR_HTTP_ENDPOINT", None)
    def test_get_api_url_default(self):
        client = DaprClient()
        self.assertEqual(
            'http://{}:{}/{}'.format(settings.DAPR_RUNTIME_HOST, settings.DAPR_HTTP_PORT,
                                     settings.DAPR_API_VERSION),
            client.invocation_client._client.get_api_url())
