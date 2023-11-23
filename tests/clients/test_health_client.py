# -*- coding: utf-8 -*-

"""
Copyright 2023 The Dapr Authors
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

from .fake_http_server import FakeHttpServer

from dapr.clients.http.helpers import DaprHealthClient
from dapr.conf import settings


class DaprHealthClientTests(unittest.TestCase):

    def setUp(self):
        self.server = FakeHttpServer()
        self.server_port = self.server.get_port()
        self.server.start()
        settings.DAPR_HTTP_PORT = self.server_port
        settings.DAPR_API_METHOD_INVOCATION_PROTOCOL = 'http'
        self.client = DaprHealthClient()
        self.app_id = 'fakeapp'

    def tearDown(self):
        self.server.shutdown_server()
        settings.DAPR_API_TOKEN = None
        settings.DAPR_API_METHOD_INVOCATION_PROTOCOL = 'http'

    def test_wait_ok(self):
        self.client.wait(1)

    def test_wait_timeout(self):
        self.server.shutdown_server()
        with self.assertRaises(Exception):
            self.client.wait(1)
