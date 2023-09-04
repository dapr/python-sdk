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

import os
import unittest

from unittest.mock import patch

import grpc

from dapr.aio.clients.grpc.client import DaprGrpcClientAsync
from tests.clients.test_dapr_async_grpc_client import DaprGrpcClientAsyncTests
from .fake_dapr_server import FakeDaprSidecar
from dapr.conf import settings


# Used temporarily, so we can trust self-signed certificates in unit tests
# until they get their own environment variable
def replacement_get_credentials_func(a):
    f = open(os.path.join(os.path.dirname(__file__), 'selfsigned.pem'), 'rb')
    creds = grpc.ssl_channel_credentials(f.read())
    f.close()

    return creds


DaprGrpcClientAsync.get_credentials = replacement_get_credentials_func


class DaprSecureGrpcClientAsyncTests(DaprGrpcClientAsyncTests):
    server_port = 443
    scheme = 'https://'

    def setUp(self):
        self._fake_dapr_server = FakeDaprSidecar()
        self._fake_dapr_server.start_secure(self.server_port)

    def tearDown(self):
        self._fake_dapr_server.stop_secure()

    @patch.object(settings, "DAPR_GRPC_ENDPOINT", "https://domain1.com:5000")
    def test_init_with_DAPR_GRPC_ENDPOINT(self):
        dapr = DaprGrpcClientAsync()
        self.assertEqual("domain1.com", dapr._hostname)
        self.assertEqual(5000, dapr._port)
        self.assertEqual("https", dapr._scheme)

    @patch.object(settings, "DAPR_GRPC_ENDPOINT", "https://domain1.com:5000")
    def test_init_with_DAPR_GRPC_ENDPOINT_and_argument(self):
        dapr = DaprGrpcClientAsync("https://domain2.com:5002")
        self.assertEqual("domain2.com", dapr._hostname)
        self.assertEqual(5002, dapr._port)
        self.assertEqual('https', dapr._scheme)

    @patch.object(settings, "DAPR_GRPC_ENDPOINT", "https://domain1.com:5000")
    @patch.object(settings, "DAPR_RUNTIME_HOST", "domain2.com")
    @patch.object(settings, "DAPR_GRPC_PORT", "5002")
    def test_init_with_DAPR_GRPC_ENDPOINT_and_DAPR_RUNTIME_HOST(self):
        dapr = DaprGrpcClientAsync()
        self.assertEqual("domain1.com", dapr._hostname)
        self.assertEqual(5000, dapr._port)
        self.assertEqual('https', dapr._scheme)

    @patch.object(settings, "DAPR_RUNTIME_HOST", "domain1.com")
    @patch.object(settings, "DAPR_GRPC_PORT", "5000")
    def test_init_with_argument_and_DAPR_GRPC_ENDPOINT_and_DAPR_RUNTIME_HOST(self):
        dapr = DaprGrpcClientAsync("https://domain2.com:5002")
        self.assertEqual("domain2.com", dapr._hostname)
        self.assertEqual(5002, dapr._port)
        self.assertEqual('https', dapr._scheme)

    async def test_dapr_api_token_insertion(self):
        pass


if __name__ == '__main__':
    unittest.main()
