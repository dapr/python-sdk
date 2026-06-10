import unittest
from unittest.mock import patch

from dapr.ext.workflow.util import get_grpc_channel_options, getAddress

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


class GetGrpcChannelOptionsTest(unittest.TestCase):
    @patch.object(settings, 'DAPR_GRPC_MAX_INBOUND_MESSAGE_SIZE_BYTES', 0)
    def test_explicit_kwarg_sets_both_directions(self):
        options = get_grpc_channel_options(8 * 1024 * 1024)
        self.assertEqual(
            [
                ('grpc.max_send_message_length', 8 * 1024 * 1024),
                ('grpc.max_receive_message_length', 8 * 1024 * 1024),
            ],
            options,
        )

    @patch.object(settings, 'DAPR_GRPC_MAX_INBOUND_MESSAGE_SIZE_BYTES', 16 * 1024 * 1024)
    def test_env_var_sets_both_directions(self):
        options = get_grpc_channel_options()
        self.assertEqual(
            [
                ('grpc.max_send_message_length', 16 * 1024 * 1024),
                ('grpc.max_receive_message_length', 16 * 1024 * 1024),
            ],
            options,
        )

    @patch.object(settings, 'DAPR_GRPC_MAX_INBOUND_MESSAGE_SIZE_BYTES', 16 * 1024 * 1024)
    def test_kwarg_takes_precedence_over_env_var(self):
        options = get_grpc_channel_options(8 * 1024 * 1024)
        self.assertEqual(
            [
                ('grpc.max_send_message_length', 8 * 1024 * 1024),
                ('grpc.max_receive_message_length', 8 * 1024 * 1024),
            ],
            options,
        )

    @patch.object(settings, 'DAPR_GRPC_MAX_INBOUND_MESSAGE_SIZE_BYTES', 0)
    def test_neither_set_returns_none(self):
        self.assertIsNone(get_grpc_channel_options())
