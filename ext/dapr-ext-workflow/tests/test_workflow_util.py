"""
Copyright 2025 The Dapr Authors
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

from dapr.ext.workflow.util import getAddress

from dapr.conf import settings


class DaprWorkflowUtilTest(unittest.TestCase):
    @patch.object(settings, 'DAPR_GRPC_ENDPOINT', '')
    def test_get_address_default(self):
        expected = f'{settings.DAPR_RUNTIME_HOST}:{settings.DAPR_GRPC_PORT}'
        self.assertEqual(expected, getAddress())

    def test_get_address_with_constructor_arguments(self):
        self.assertEqual('test.com:5000', getAddress('test.com', '5000'))

    def test_get_address_with_partial_constructor_arguments(self):
        expected = f'{settings.DAPR_RUNTIME_HOST}:5000'
        self.assertEqual(expected, getAddress(port='5000'))

        expected = f'test.com:{settings.DAPR_GRPC_PORT}'
        self.assertEqual(expected, getAddress(host='test.com'))

    @patch.object(settings, 'DAPR_GRPC_ENDPOINT', 'https://domain1.com:5000')
    def test_get_address_with_constructor_arguments_and_env_variable(self):
        self.assertEqual('test.com:5000', getAddress('test.com', '5000'))

    @patch.object(settings, 'DAPR_GRPC_ENDPOINT', 'https://domain1.com:5000')
    def test_get_address_with_env_variable(self):
        self.assertEqual('https://domain1.com:5000', getAddress())
