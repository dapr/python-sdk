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

from dapr.clients.http.client import DaprHttpClient
from .certs import CERTIFICATE_CHAIN_PATH
from .fake_http_server import FakeHttpServer
from dapr.conf import settings
from dapr.clients import DaprClient

from .test_http_service_invocation_client import DaprInvocationHttpClientTests


def replacement_get_ssl_context(a):
    return ssl.create_default_context(purpose=ssl.Purpose.SERVER_AUTH,
                                      capath=CERTIFICATE_CHAIN_PATH)


DaprHttpClient.get_ssl_context = replacement_get_ssl_context


class DaprSecureInvocationHttpClientTests(DaprInvocationHttpClientTests):
    def setUp(self):
        self.server = FakeHttpServer(True)
        self.server_port = self.server.get_port()
        self.server.start()
        settings.DAPR_HTTP_PORT = self.server_port
        settings.DAPR_API_METHOD_INVOCATION_PROTOCOL = 'http'
        self.client = DaprClient("https://localhost:{}".format(self.server_port))
        self.app_id = 'fakeapp'
        self.method_name = 'fakemethod'
        self.invoke_url = f'/v1.0/invoke/{self.app_id}/method/{self.method_name}'

    def tearDown(self):
        self.server.shutdown_secure_server()
        settings.DAPR_API_TOKEN = None
        settings.DAPR_API_METHOD_INVOCATION_PROTOCOL = 'http'
