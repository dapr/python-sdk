# -*- coding: utf-8 -*-

"""
Copyright 2026 The Dapr Authors
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

import io
import unittest
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import MagicMock, patch

import grpc
import pytest

from dapr.clients import DaprClient
from dapr.clients.exceptions import DaprGrpcError
from dapr.clients.grpc._binarystore import BinaryFileResponse, _BinaryFileUpload
from dapr.clients.grpc._crypto import EncryptOptions
from dapr.clients.grpc.client import DaprGrpcClient
from dapr.clients.retry import RetryPolicy
from dapr.conf import settings
from dapr.proto import api_v1, common_v1
from dapr.proto.runtime.v1 import binarystore_pb2 as binary_v1
from tests.clients.binarystore_server import BinaryStoreSidecar

pytestmark = pytest.mark.filterwarnings('ignore:The Binary Store API:UserWarning')


def message(data, seq=0):
    return binary_v1.GetBinaryFileResponseAlpha1(
        payload=common_v1.StreamPayload(data=data, seq=seq)
    )


class BinaryFileReaderTests(unittest.TestCase):
    def response(self, *messages):
        stream = MagicMock()
        stream.__iter__.return_value = iter(messages)
        return BinaryFileResponse(stream), stream

    def test_partial_reads_iteration_and_read_all_share_one_cursor(self):
        response, _ = self.response(message(b'abc'), message(b'def', 1), message(b'ghi', 2))
        self.assertEqual(b'', response.read(0))
        self.assertEqual(b'a', response.read(1))
        self.assertEqual(b'b', response.read(1))
        self.assertEqual(b'c', next(response))
        self.assertEqual(b'de', response.read(2))
        self.assertEqual(b'fghi', response.read())
        self.assertEqual(b'', response.read())
        self.assertEqual([], list(response))

    def test_read_sizes_empty_chunks_and_eof(self):
        response, _ = self.response(message(b''), message(b'abc', 1))
        self.assertEqual(b'abc', response.read(20))
        self.assertEqual(b'', response.read(-2))
        with self.assertRaises(TypeError):
            response.read(1.5)

    def test_invalid_sequence_or_missing_payload_cancels(self):
        for invalid in [message(b'x', 1), binary_v1.GetBinaryFileResponseAlpha1()]:
            with self.subTest(message=invalid):
                response, stream = self.response(invalid)
                with self.assertRaises(ValueError):
                    response.read()
                stream.cancel.assert_called_once()

    def test_close_context_exit_and_eof(self):
        response, stream = self.response(message(b'abc'))
        with response:
            self.assertEqual(b'a', response.read(1))
        response.close()
        stream.cancel.assert_called_once()
        with self.assertRaises(ValueError):
            response.read()
        response, stream = self.response()
        self.assertEqual(b'', response.read())
        response.close()
        stream.cancel.assert_not_called()

    def test_upload_validation_and_initial_before_any_read(self):
        reader = MagicMock()
        source = _BinaryFileUpload('files', 'file', reader, False, 2)
        initial = next(iter(source))
        self.assertEqual('initial_request', initial.WhichOneof('set_binary_file_request_type'))
        reader.read.assert_not_called()
        for size in [0, -1, True, 1.5]:
            with self.subTest(size=size), self.assertRaises((TypeError, ValueError)):
                _BinaryFileUpload('files', 'file', b'', False, size)
        for data in ['text', io.StringIO('text'), 42]:
            with self.subTest(data=data), self.assertRaises(TypeError):
                _BinaryFileUpload('files', 'file', data, False, 2)

    def test_close_generator_releases_stream(self):
        closed = []

        def stream():
            try:
                yield message(b'abc')
                yield message(b'def', 1)
            finally:
                closed.append(True)

        response = BinaryFileResponse(stream())
        self.assertEqual(b'a', response.read(1))
        response.close()
        response.close()
        self.assertEqual([True], closed)


class BinaryStoreClientTests(unittest.TestCase):
    def setUp(self):
        self.server = BinaryStoreSidecar()
        self.server.start()
        self.addCleanup(self.server.stop)
        health = patch('dapr.clients.grpc.client.DaprHealth.wait_for_sidecar')
        health.start()
        self.addCleanup(health.stop)
        self.client = DaprGrpcClient(f'127.0.0.1:{self.server.grpc_port}')
        self.addCleanup(self.client.close)

    def test_public_client_inherits_methods(self):
        self.assertIs(DaprClient.get_binary_file_alpha1, DaprGrpcClient.get_binary_file_alpha1)

    def test_framing_binary_round_trip_custom_chunks_and_headers(self):
        payload = bytes(range(256)) * 257
        result = self.client.set_binary_file_alpha1('files', 'nested/file', payload)
        messages = self.server.uploads[0]
        self.assertEqual('initial_request', messages[0].WhichOneof('set_binary_file_request_type'))
        self.assertFalse(messages[0].initial_request.overwrite)
        self.assertEqual([0, 1, 2], [m.payload.seq for m in messages[1:]])
        self.assertEqual([32768, 32768, 256], [len(m.payload.data) for m in messages[1:]])
        self.assertEqual(['value'], result.headers['binary-header'])
        with self.client.get_binary_file_alpha1('files', 'nested/file') as response:
            self.assertEqual(payload, response.read())
        source = io.BytesIO(b'prefix\x00\xff\x80')
        source.seek(6)
        self.client.set_binary_file_alpha1(
            'files', 'nested/file', source, overwrite=True, chunk_size=2
        )
        self.assertFalse(source.closed)
        self.assertEqual(
            b'\x00\xff\x80', self.client.get_binary_file_alpha1('files', 'nested/file').read()
        )
        self.assertTrue(self.server.uploads[-1][0].initial_request.overwrite)
        self.assertEqual(
            ['value'],
            self.client.delete_binary_file_alpha1('files', 'nested/file').headers['binary-header'],
        )

    def test_empty_upload_and_no_replay_on_server_rejection(self):
        self.client.retry_policy = RetryPolicy(max_attempts=3)
        self.client.set_binary_file_alpha1('files', 'empty', b'')
        self.assertEqual(1, len(self.server.uploads[0]))
        self.assertEqual(b'', self.client.get_binary_file_alpha1('files', 'empty').read())
        for code in [
            grpc.StatusCode.ALREADY_EXISTS,
            grpc.StatusCode.UNAVAILABLE,
            grpc.StatusCode.UNIMPLEMENTED,
        ]:
            self.server.upload_error = code
            before = len(self.server.uploads)
            with self.assertRaises(DaprGrpcError) as caught:
                self.client.set_binary_file_alpha1('files', 'file', b'x' * 65536)
            self.assertEqual(code, caught.exception.code())
            self.assertEqual(before + 1, len(self.server.uploads))

    def test_local_reader_failures_short_reads_and_no_unbounded_reads(self):
        failure = OSError('disk read failed')
        reader = MagicMock()
        reader.read.side_effect = [b'ab', failure]
        with self.assertRaises(OSError) as caught:
            self.client.set_binary_file_alpha1('files', 'file', reader, chunk_size=4)
        self.assertIs(failure, caught.exception)
        reader.close.assert_not_called()
        reader.read.side_effect = [b'a', b'b', b'']
        self.client.set_binary_file_alpha1('files', 'short', reader, chunk_size=4)
        self.assertEqual(b'ab', self.server.files[('files', 'short')])
        self.assertTrue(all(call.args == (4,) for call in reader.read.call_args_list))
        for returned in ['text', None, b'too long']:
            reader.read.side_effect = None
            reader.read.return_value = returned
            with self.subTest(returned=returned), self.assertRaises((TypeError, ValueError)):
                self.client.set_binary_file_alpha1('files', 'bad', reader, chunk_size=4)

    def test_success_waits_for_server_completion(self):
        self.server.wait_for_upload = True
        with ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(self.client.set_binary_file_alpha1, 'files', 'file', b'x')
            try:
                self.assertTrue(self.server.upload_received.wait(5))
                self.assertFalse(future.done())
            finally:
                self.server.upload_release.set()
            future.result(timeout=5)

    def test_partial_download_error_and_missing_file_preserve_status(self):
        self.server.files[('files', 'file')] = b'abc'
        self.server.download_error = grpc.StatusCode.UNAVAILABLE
        response = self.client.get_binary_file_alpha1('files', 'file')
        self.assertEqual(b'abc', next(response))
        with self.assertRaises(DaprGrpcError) as caught:
            next(response)
        self.assertEqual(grpc.StatusCode.UNAVAILABLE, caught.exception.code())
        with self.assertRaises(DaprGrpcError) as caught:
            self.client.get_binary_file_alpha1('files', 'missing').read()
        self.assertEqual(grpc.StatusCode.NOT_FOUND, caught.exception.code())
        with self.assertRaises(DaprGrpcError):
            self.client.delete_binary_file_alpha1('files', 'missing')

    def test_early_close_cancels_actual_rpc(self):
        self.server.files[('files', 'file')] = b'abc'
        self.server.hold_download = True
        with self.client.get_binary_file_alpha1('files', 'file') as response:
            self.assertEqual(b'abc', next(response))
        self.assertTrue(self.server.download_cancelled.wait(5))
        self.client.set_binary_file_alpha1('files', 'still-usable', b'ok')

    def test_client_shutdown_cancels_download(self):
        self.server.files[('files', 'file')] = b'abc'
        self.server.hold_download = True
        response = self.client.get_binary_file_alpha1('files', 'file')
        self.assertEqual(b'abc', response.read(3))
        self.client.close()
        with self.assertRaises(DaprGrpcError) as caught:
            response.read()
        self.assertEqual(grpc.StatusCode.CANCELLED, caught.exception.code())
        self.assertTrue(self.server.download_cancelled.wait(5))

    def test_deadline_and_invalid_arguments(self):
        self.server.wait_for_upload = True
        with self.assertRaises(DaprGrpcError) as caught:
            self.client.set_binary_file_alpha1('files', 'file', b'x', timeout=0.05)
        self.assertEqual(grpc.StatusCode.DEADLINE_EXCEEDED, caught.exception.code())
        self.server.upload_release.set()
        for store, name in [('', 'file'), ('files', ' '), (None, 'file')]:
            for method in [
                self.client.get_binary_file_alpha1,
                self.client.delete_binary_file_alpha1,
            ]:
                with (
                    self.subTest(store=store, name=name),
                    self.assertRaises((TypeError, ValueError)),
                ):
                    method(store, name)
        with self.assertWarnsRegex(UserWarning, 'Alpha'):
            self.client.set_binary_file_alpha1('files', 'warn', b'')

    @patch.object(settings, 'DAPR_API_TOKEN', 'test-token')
    @patch.object(settings, 'DAPR_API_TIMEOUT_SECONDS', 7)
    def test_token_metadata_and_timeout_through_real_channel(self):
        self.server.token = 'test-token'
        with DaprGrpcClient(f'127.0.0.1:{self.server.grpc_port}') as client:
            client.set_binary_file_alpha1('files', 'file', b'hello')
            self.assertEqual(b'hello', client.get_binary_file_alpha1('files', 'file').read())
            client.delete_binary_file_alpha1('files', 'file', timeout=3)
            self.assertEqual(
                b'ABC', client.encrypt(b'abc', EncryptOptions('crypto', 'key', 'RSA')).read()
            )
        self.assertEqual(['set', 'get', 'delete', 'encrypt'], [c[0] for c in self.server.calls])
        for method, metadata, deadline in self.server.calls:
            self.assertEqual(1, metadata.count(('dapr-api-token', 'test-token')))
            if method in ['set', 'get']:
                self.assertGreater(deadline, 5)
                self.assertLessEqual(deadline, 7.1)
            elif method == 'delete':
                self.assertLessEqual(deadline, 3.1)

    @patch.object(settings, 'DAPR_API_TOKEN', 'test-token')
    def test_existing_configuration_stream_sends_one_token(self):
        self.server.token = 'test-token'
        cases = [(), (('custom-header', 'first'), ('another-header', 'second'))]
        cases.append((*cases[-1], ('dapr-api-token', 'test-token')))
        cases.append((*cases[1], ('dapr-api-token', 'caller-token')))
        with DaprGrpcClient(f'127.0.0.1:{self.server.grpc_port}') as client:
            for rpc in ['SubscribeConfiguration', 'SubscribeConfigurationAlpha1']:
                for metadata in cases:
                    with self.subTest(rpc=rpc, metadata=metadata):
                        token = dict(metadata).get('dapr-api-token', 'test-token')
                        self.server.token = token
                        responses = list(
                            getattr(client._stub, rpc)(
                                api_v1.SubscribeConfigurationRequest(store_name='configuration'),
                                metadata=metadata,
                            )
                        )
                        self.assertEqual('configuration-subscription', responses[0].id)
                        method, headers, _ = self.server.calls[-1]
                        self.assertEqual('configuration', method)
                        self.assertEqual(
                            [('dapr-api-token', token)],
                            [header for header in headers if header[0] == 'dapr-api-token'],
                        )
                        for header in metadata:
                            self.assertIn(header, headers)

    @patch.object(settings, 'DAPR_API_TOKEN', 'test-token')
    def test_invalid_caller_token_does_not_fall_back_to_default(self):
        self.server.token = 'test-token'
        with DaprGrpcClient(f'127.0.0.1:{self.server.grpc_port}') as client:
            for token in ['invalid-token', '']:
                with self.subTest(token=token):
                    with self.assertRaises(grpc.RpcError) as caught:
                        list(
                            client._stub.SubscribeConfiguration(
                                api_v1.SubscribeConfigurationRequest(store_name='configuration'),
                                metadata=(('dapr-api-token', token),),
                            )
                        )
                    self.assertEqual(grpc.StatusCode.UNAUTHENTICATED, caught.exception.code())
                    headers = self.server.calls[-1][1]
                    self.assertEqual(
                        [('dapr-api-token', token)],
                        [header for header in headers if header[0] == 'dapr-api-token'],
                    )

    @patch.object(settings, 'DAPR_API_TOKEN', 'test-token')
    def test_caller_token_overrides_default_for_all_rpc_shapes(self):
        self.server.token = 'caller-token'
        metadata = (('custom-header', 'custom-value'), ('dapr-api-token', 'caller-token'))
        with DaprGrpcClient(f'127.0.0.1:{self.server.grpc_port}') as client:
            client._stub.SetBinaryFileAlpha1(
                iter(_BinaryFileUpload('files', 'metadata', b'x', False, 32768)),
                metadata=metadata,
            )
            list(
                client._stub.GetBinaryFileAlpha1(
                    binary_v1.GetBinaryFileRequestAlpha1(
                        component_name='files', file_name='metadata'
                    ),
                    metadata=metadata,
                )
            )
            client._stub.DeleteBinaryFileAlpha1(
                binary_v1.DeleteBinaryFileRequestAlpha1(
                    component_name='files', file_name='metadata'
                ),
                metadata=metadata,
            )
            list(
                client._stub.EncryptAlpha1(
                    iter([api_v1.EncryptRequest(payload=common_v1.StreamPayload(data=b'abc'))]),
                    metadata=metadata,
                )
            )
        self.assertEqual(['set', 'get', 'delete', 'encrypt'], [c[0] for c in self.server.calls])
        for _, headers, _ in self.server.calls:
            self.assertEqual(
                [('dapr-api-token', 'caller-token')],
                [header for header in headers if header[0] == 'dapr-api-token'],
            )
            self.assertIn(('custom-header', 'custom-value'), headers)
