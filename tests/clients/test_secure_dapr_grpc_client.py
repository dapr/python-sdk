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

from tests.clients.test_dapr_grpc_client import DaprGrpcClientTests
from .fake_dapr_server import FakeDaprSidecar


class DaprSecureGrpcClientTests(DaprGrpcClientTests):
    server_port = 443

    def setUp(self):
        self._fake_dapr_server = FakeDaprSidecar()
        self._fake_dapr_server.start_secure(self.server_port)
        print("Fake Secure Dapr server started")

    def tearDown(self):
        self._fake_dapr_server.stop()
        self._fake_dapr_server.clean_up_certs()


if __name__ == '__main__':
    unittest.main()
