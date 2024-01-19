import unittest
from dapr.ext.workflow.util import getAddress
from unittest.mock import patch

from dapr.conf import settings


class DaprWorkflowUtilTest(unittest.TestCase):
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
