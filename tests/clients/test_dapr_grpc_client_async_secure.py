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

from unittest.mock import patch

from dapr.aio.clients.grpc.client import DaprGrpcClientAsync
from dapr.clients.health import DaprHealth
from tests.clients.certs import replacement_get_credentials_func, replacement_get_health_context
from tests.clients.test_dapr_grpc_client_async import DaprGrpcClientAsyncTests
from .fake_dapr_server import FakeDaprSidecar
from dapr.conf import settings


DaprGrpcClientAsync.get_credentials = replacement_get_credentials_func
DaprHealth.get_ssl_context = replacement_get_health_context


class DaprSecureGrpcClientAsyncTests(DaprGrpcClientAsyncTests):
    grpc_port = 50001
    http_port = 4443  # The http server is used for health checks only, and doesn't need TLS
    scheme = 'https://'

    @classmethod
    def setUpClass(cls):
        cls._fake_dapr_server = FakeDaprSidecar(grpc_port=cls.grpc_port, http_port=cls.http_port)
        cls._fake_dapr_server.start_secure()
        settings.DAPR_HTTP_PORT = cls.http_port
        settings.DAPR_HTTP_ENDPOINT = 'https://127.0.0.1:{}'.format(cls.http_port)

    @classmethod
    def tearDownClass(cls):
        cls._fake_dapr_server.stop_secure()

    @patch.object(settings, 'DAPR_GRPC_ENDPOINT', 'dns:domain1.com:5000')
    def test_init_with_DAPR_GRPC_ENDPOINT(self):
        dapr = DaprGrpcClientAsync()
        self.assertEqual('dns:domain1.com:5000', dapr._uri.endpoint)

    @patch.object(settings, 'DAPR_GRPC_ENDPOINT', 'dns:domain1.com:5000')
    def test_init_with_DAPR_GRPC_ENDPOINT_and_argument(self):
        dapr = DaprGrpcClientAsync('dns:domain2.com:5002')
        self.assertEqual('dns:domain2.com:5002', dapr._uri.endpoint)

    @patch.object(settings, 'DAPR_GRPC_ENDPOINT', 'dns:domain1.com:5000')
    @patch.object(settings, 'DAPR_RUNTIME_HOST', 'domain2.com')
    @patch.object(settings, 'DAPR_GRPC_PORT', '5002')
    def test_init_with_DAPR_GRPC_ENDPOINT_and_DAPR_RUNTIME_HOST(self):
        dapr = DaprGrpcClientAsync()
        self.assertEqual('dns:domain1.com:5000', dapr._uri.endpoint)

    @patch.object(settings, 'DAPR_RUNTIME_HOST', 'domain1.com')
    @patch.object(settings, 'DAPR_GRPC_PORT', '5000')
    def test_init_with_argument_and_DAPR_GRPC_ENDPOINT_and_DAPR_RUNTIME_HOST(self):
        dapr = DaprGrpcClientAsync('dns:domain2.com:5002')
        self.assertEqual('dns:domain2.com:5002', dapr._uri.endpoint)

    async def test_dapr_api_token_insertion(self):
        pass


if __name__ == '__main__':
    unittest.main()
