import unittest

import grpc
from google.rpc import error_details_pb2, status_pb2, code_pb2
from google.protobuf.any_pb2 import Any
from google.protobuf.duration_pb2 import Duration

from dapr.clients import DaprGrpcClient
from dapr.clients.exceptions import DaprGrpcError
from dapr.conf import settings

from .fake_dapr_server import FakeDaprSidecar


def create_expected_status():
    detail1 = Any()
    detail1.Pack(error_details_pb2.ErrorInfo(reason='DAPR_ERROR_CODE'))

    detail2 = Any()
    detail2.Pack(
        error_details_pb2.ResourceInfo(
            resource_type='my_resource_type', resource_name='my_resource'
        )
    )

    detail3 = Any()
    detail3.Pack(
        error_details_pb2.BadRequest(
            field_violations=[
                error_details_pb2.BadRequest.FieldViolation(
                    field='my_field', description='my field violation message'
                )
            ]
        )
    )

    detail4 = Any()
    help_message = error_details_pb2.Help()
    link = error_details_pb2.Help.Link(description='Help Link', url='https://my_help_link')
    help_message.links.extend([link])
    detail4.Pack(help_message)

    detail5 = Any()
    retry_info = error_details_pb2.RetryInfo(retry_delay=Duration(seconds=5))
    detail5.Pack(retry_info)

    detail6 = Any()
    detail6.Pack(error_details_pb2.DebugInfo(stack_entries=['stack_entry_1', 'stack_entry_2']))

    detail7 = Any()
    detail7.Pack(error_details_pb2.LocalizedMessage(locale='en-US', message='my localized message'))

    detail8 = Any()
    violation = error_details_pb2.PreconditionFailure.Violation(
        type='your_violation_type',
        subject='your_violation_subject',
        description='your_violation_description',
    )
    detail8.Pack(error_details_pb2.PreconditionFailure(violations=[violation]))

    detail9 = Any()
    violation = error_details_pb2.QuotaFailure.Violation(
        subject='your_violation_subject', description='your_violation_description'
    )
    detail9.Pack(error_details_pb2.QuotaFailure(violations=[violation]))

    detail10 = Any()
    detail10.Pack(
        error_details_pb2.RequestInfo(
            request_id='your_request_id', serving_data='your_serving_data'
        )
    )

    return status_pb2.Status(
        code=code_pb2.INTERNAL,
        message='my invalid argument message',
        details=[
            detail1,
            detail2,
            detail3,
            detail4,
            detail5,
            detail6,
            detail7,
            detail8,
            detail9,
            detail10,
        ],
    )


class DaprExceptionsTestCase(unittest.TestCase):
    _grpc_port = 50001
    _http_port = 3500

    @classmethod
    def setUpClass(cls):
        cls._fake_dapr_server = FakeDaprSidecar(grpc_port=cls._grpc_port, http_port=cls._http_port)
        settings.DAPR_HTTP_PORT = cls._http_port
        settings.DAPR_HTTP_ENDPOINT = 'http://127.0.0.1:{}'.format(cls._http_port)
        cls._fake_dapr_server.start()
        cls._expected_status = create_expected_status()

    @classmethod
    def tearDownClass(cls):
        cls._fake_dapr_server.stop()

    def test_exception_status_parsing(self):
        dapr = DaprGrpcClient(f'localhost:{self._grpc_port}')

        self._fake_dapr_server.raise_exception_on_next_call(self._expected_status)
        with self.assertRaises(DaprGrpcError) as context:
            dapr.get_metadata()

        dapr_error = context.exception

        self.assertEqual(dapr_error.code(), grpc.StatusCode.INTERNAL)
        self.assertEqual(dapr_error.details(), 'my invalid argument message')
        self.assertEqual(dapr_error.error_code(), 'DAPR_ERROR_CODE')

        self.assertIsNotNone(dapr_error._details.error_info)
        self.assertEqual(dapr_error.status_details().error_info['reason'], 'DAPR_ERROR_CODE')
        #
        self.assertIsNotNone(dapr_error.status_details().resource_info)
        self.assertEqual(
            dapr_error.status_details().resource_info['resource_type'], 'my_resource_type'
        )
        self.assertEqual(dapr_error.status_details().resource_info['resource_name'], 'my_resource')

        self.assertIsNotNone(dapr_error.status_details().bad_request)
        self.assertEqual(len(dapr_error.status_details().bad_request['field_violations']), 1)
        self.assertEqual(
            dapr_error.status_details().bad_request['field_violations'][0]['field'], 'my_field'
        )
        self.assertEqual(
            dapr_error.status_details().bad_request['field_violations'][0]['description'],
            'my field violation message',
        )

        self.assertIsNotNone(dapr_error.status_details().help)
        self.assertEqual(
            dapr_error.status_details().help['links'][0]['url'], 'https://my_help_link'
        )

        self.assertIsNotNone(dapr_error.status_details().retry_info)
        self.assertEqual(dapr_error.status_details().retry_info['retry_delay'], '5s')

        self.assertIsNotNone(dapr_error.status_details().debug_info)
        self.assertEqual(len(dapr_error.status_details().debug_info['stack_entries']), 2)
        self.assertEqual(
            dapr_error.status_details().debug_info['stack_entries'][0], 'stack_entry_1'
        )
        self.assertEqual(
            dapr_error.status_details().debug_info['stack_entries'][1], 'stack_entry_2'
        )

        self.assertIsNotNone(dapr_error.status_details().localized_message)
        self.assertEqual(dapr_error.status_details().localized_message['locale'], 'en-US')
        self.assertEqual(
            dapr_error.status_details().localized_message['message'], 'my localized message'
        )

        self.assertIsNotNone(dapr_error.status_details().precondition_failure)
        self.assertEqual(len(dapr_error.status_details().precondition_failure['violations']), 1)
        self.assertEqual(
            dapr_error.status_details().precondition_failure['violations'][0]['type'],
            'your_violation_type',
        )
        self.assertEqual(
            dapr_error.status_details().precondition_failure['violations'][0]['subject'],
            'your_violation_subject',
        )
        self.assertEqual(
            dapr_error.status_details().precondition_failure['violations'][0]['description'],
            'your_violation_description',
        )

        self.assertIsNotNone(dapr_error.status_details().quota_failure)
        self.assertEqual(len(dapr_error.status_details().quota_failure['violations']), 1)
        self.assertEqual(
            dapr_error.status_details().quota_failure['violations'][0]['subject'],
            'your_violation_subject',
        )
        self.assertEqual(
            dapr_error.status_details().quota_failure['violations'][0]['description'],
            'your_violation_description',
        )

        self.assertIsNotNone(dapr_error.status_details().request_info)
        self.assertEqual(dapr_error.status_details().request_info['request_id'], 'your_request_id')
        self.assertEqual(
            dapr_error.status_details().request_info['serving_data'], 'your_serving_data'
        )

    def test_error_code(self):
        dapr = DaprGrpcClient(f'localhost:{self._grpc_port}')

        expected_status = create_expected_status()

        self._fake_dapr_server.raise_exception_on_next_call(expected_status)
        with self.assertRaises(DaprGrpcError) as context:
            dapr.get_metadata()

        dapr_error = context.exception

        self.assertEqual(dapr_error.error_code(), 'DAPR_ERROR_CODE')

        # No ErrorInfo
        self._fake_dapr_server.raise_exception_on_next_call(
            status_pb2.Status(code=code_pb2.INTERNAL, message='my invalid argument message')
        )

        with self.assertRaises(DaprGrpcError) as context:
            dapr.get_metadata()

        dapr_error = context.exception

        self.assertEqual(dapr_error.error_code(), 'UNKNOWN')
