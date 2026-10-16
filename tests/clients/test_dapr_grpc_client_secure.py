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

from dapr.clients.grpc.client import DaprGrpcClient
from dapr.clients.health import DaprHealth
from dapr.conf import settings
from tests.clients import test_dapr_grpc_client as base
from tests.clients.certs import replacement_get_credentials_func, replacement_get_health_context

from .fake_dapr_server import FakeDaprSidecar
from .fake_http_server import point_settings_at_http_port


# The base class is reached through its module so pytest does not collect it a second
# time in this file.
class DaprSecureGrpcClientTests(base.DaprGrpcClientTests):
    scheme = 'https://'

    DaprGrpcClient.get_credentials = replacement_get_credentials_func
    DaprHealth.get_ssl_context = replacement_get_health_context

    @classmethod
    def setUpClass(cls):
        cls._fake_dapr_server = FakeDaprSidecar()
        cls.addClassCleanup(cls._fake_dapr_server.stop_secure)
        cls._fake_dapr_server.start_secure()
        cls.grpc_port = cls._fake_dapr_server.grpc_port
        cls.http_port = cls._fake_dapr_server.http_port
        point_settings_at_http_port(cls, cls.http_port, scheme='https')

    @patch.object(settings, 'DAPR_GRPC_ENDPOINT', 'https://domain1.com:5000')
    def test_init_with_DAPR_GRPC_ENDPOINT(self):
        dapr = DaprGrpcClient()
        self.assertEqual('dns:domain1.com:5000', dapr._uri.endpoint)

    @patch.object(settings, 'DAPR_GRPC_ENDPOINT', 'https://domain1.com:5000')
    def test_init_with_DAPR_GRPC_ENDPOINT_and_argument(self):
        dapr = DaprGrpcClient('https://domain2.com:5002')
        self.assertEqual('dns:domain2.com:5002', dapr._uri.endpoint)

    @patch.object(settings, 'DAPR_GRPC_ENDPOINT', 'https://domain1.com:5000')
    @patch.object(settings, 'DAPR_RUNTIME_HOST', 'domain2.com')
    @patch.object(settings, 'DAPR_GRPC_PORT', '5002')
    def test_init_with_DAPR_GRPC_ENDPOINT_and_DAPR_RUNTIME_HOST(self):
        dapr = DaprGrpcClient()
        self.assertEqual('dns:domain1.com:5000', dapr._uri.endpoint)

    @patch.object(settings, 'DAPR_RUNTIME_HOST', 'domain1.com')
    @patch.object(settings, 'DAPR_GRPC_PORT', '5000')
    def test_init_with_argument_and_DAPR_GRPC_ENDPOINT_and_DAPR_RUNTIME_HOST(self):
        dapr = DaprGrpcClient('https://domain2.com:5002')
        self.assertEqual('dns:domain2.com:5002', dapr._uri.endpoint)


if __name__ == '__main__':
    unittest.main()
