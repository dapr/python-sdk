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

import asyncio
import io
import threading
import unittest
from unittest.mock import MagicMock, patch

import grpc
import pytest

from dapr.aio.clients import DaprClient
from dapr.aio.clients.grpc._binarystore import AsyncBinaryFileResponse
from dapr.aio.clients.grpc.client import DaprGrpcClientAsync
from dapr.clients.exceptions import DaprGrpcError
from dapr.clients.grpc._binarystore import _BinaryFileUpload
from dapr.clients.retry import RetryPolicy
from dapr.conf import settings
from dapr.proto.runtime.v1 import binarystore_pb2 as binary_v1
from tests.clients.binarystore_server import BinaryStoreSidecar
from tests.clients.test_binarystore import message

pytestmark = pytest.mark.filterwarnings('ignore:The Binary Store API:UserWarning')


class AsyncMessages:
    def __init__(self, messages):
        self.messages = iter(messages)
        self.cancel = MagicMock()

    def __aiter__(self):
        return self

    async def __anext__(self):
        try:
            return next(self.messages)
        except StopIteration:
            raise StopAsyncIteration


class AsyncBinaryFileReaderTests(unittest.IsolatedAsyncioTestCase):
    async def test_partial_reads_iteration_and_read_all_share_cursor(self):
        response = AsyncBinaryFileResponse(AsyncMessages([message(b'abc'), message(b'def', 1)]))
        self.assertEqual(b'', await response.read(0))
        self.assertEqual(b'a', await response.read(1))
        self.assertEqual(b'b', await response.read(1))
        self.assertEqual(b'c', await response.__anext__())
        self.assertEqual(b'd', await response.read(1))
        self.assertEqual(b'ef', await response.read())
        self.assertEqual(b'', await response.read())
        self.assertEqual([], [chunk async for chunk in response])
        await response.aclose()

    async def test_invalid_sequence_missing_payload_and_close(self):
        for invalid in [message(b'x', 1), binary_v1.GetBinaryFileResponseAlpha1()]:
            stream = AsyncMessages([invalid])
            response = AsyncBinaryFileResponse(stream)
            with self.subTest(message=invalid), self.assertRaises(ValueError):
                await response.read()
            stream.cancel.assert_called_once()
        stream = AsyncMessages([message(b'abc')])
        async with AsyncBinaryFileResponse(stream) as response:
            self.assertEqual(b'a', await response.read(1))
        await response.aclose()
        stream.cancel.assert_called_once()
        with self.assertRaises(ValueError):
            await response.read()

    async def test_negative_sizes_empty_chunks_and_eof(self):
        stream = AsyncMessages([message(b''), message(b'abc', 1)])
        response = AsyncBinaryFileResponse(stream)
        with self.assertRaises(TypeError):
            await response.read(1.5)
        self.assertEqual(b'abc', await response.read(-2))
        self.assertEqual(b'', await response.read(100))
        await response.aclose()
        stream.cancel.assert_not_called()


class AsyncBinaryStoreClientTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.server = BinaryStoreSidecar()
        self.server.start()
        self.addCleanup(self.server.stop)
        health = patch('dapr.clients.grpc.client.DaprHealth.wait_for_sidecar')
        health.start()
        self.addCleanup(health.stop)
        self.client = DaprGrpcClientAsync(f'127.0.0.1:{self.server.grpc_port}')
        self.addAsyncCleanup(self.client.close)

    def test_public_client_inherits_methods(self):
        self.assertIs(DaprClient.get_binary_file_alpha1, DaprGrpcClientAsync.get_binary_file_alpha1)

    async def test_framing_round_trip_empty_file_and_metadata(self):
        data = bytes(range(256)) * 257
        result = await self.client.set_binary_file_alpha1('files', 'file', data)
        self.assertEqual(['value'], result.headers['binary-header'])
        messages = self.server.uploads[0]
        self.assertEqual('initial_request', messages[0].WhichOneof('set_binary_file_request_type'))
        self.assertEqual([0, 1, 2], [m.payload.seq for m in messages[1:]])
        self.assertEqual([32768, 32768, 256], [len(m.payload.data) for m in messages[1:]])
        response = await self.client.get_binary_file_alpha1('files', 'file')
        async with response:
            self.assertEqual(data, await response.read())
        source = io.BytesIO(b'prefix\x00\xff\x80')
        source.seek(6)
        await self.client.set_binary_file_alpha1(
            'files', 'file', source, overwrite=True, chunk_size=2
        )
        self.assertFalse(source.closed)
        self.assertTrue(self.server.uploads[-1][0].initial_request.overwrite)
        result = await self.client.delete_binary_file_alpha1('files', 'file')
        self.assertEqual(['value'], result.headers['binary-header'])
        await self.client.set_binary_file_alpha1('files', 'empty', b'')
        self.assertEqual(1, len(self.server.uploads[-1]))
        response = await self.client.get_binary_file_alpha1('files', 'empty')
        self.assertEqual(b'', await response.read())

    async def test_source_errors_leave_caller_input_open(self):
        failure = OSError('disk read failed')
        source = MagicMock()
        source.read.side_effect = [b'a', failure]
        with self.assertRaises(OSError) as caught:
            await self.client.set_binary_file_alpha1('files', 'file', source, chunk_size=2)
        self.assertIs(failure, caught.exception)
        source.close.assert_not_called()

    async def test_server_rejection_preserves_available_status_without_replay(self):
        self.client.retry_policy = RetryPolicy(max_attempts=3)
        for code in [
            grpc.StatusCode.ALREADY_EXISTS,
            grpc.StatusCode.RESOURCE_EXHAUSTED,
            grpc.StatusCode.UNAVAILABLE,
            grpc.StatusCode.UNIMPLEMENTED,
        ]:
            # Test both rejection of the initial message and failure after a
            # multi-chunk body. Concurrent writes during an early abort can
            # mask the server's status in grpc.aio itself (grpc/grpc#36066).
            for early in [True, False]:
                self.server.upload_error = code if early else None
                self.server.upload_error_after_body = None if early else code
                before = len(self.server.uploads)
                with (
                    self.subTest(code=code, early=early),
                    self.assertRaises(DaprGrpcError) as caught,
                ):
                    await self.client.set_binary_file_alpha1(
                        'files', 'file', b'' if early else b'x' * 100000
                    )
                self.assertEqual(code, caught.exception.code(), caught.exception.details())
                self.assertEqual(before + 1, len(self.server.uploads))

    async def test_upload_completion_and_caller_cancellation(self):
        self.server.wait_for_upload = True
        task = asyncio.create_task(self.client.set_binary_file_alpha1('files', 'file', b'x'))
        try:
            self.assertTrue(await asyncio.to_thread(self.server.upload_received.wait, 5))
            self.assertFalse(task.done())
            task.cancel()
            with self.assertRaises(asyncio.CancelledError):
                await task
        finally:
            self.server.upload_release.set()
        self.assertTrue(task.cancelled())

    async def test_blocking_file_read_does_not_block_event_loop_or_continue_after_cancel(self):
        entered = threading.Event()
        release = threading.Event()
        source = MagicMock()

        def read(size):
            entered.set()
            release.wait(5)
            return b'x'

        source.read.side_effect = read
        task = asyncio.create_task(self.client.set_binary_file_alpha1('files', 'file', source))
        try:
            self.assertTrue(await asyncio.to_thread(entered.wait, 5))
            # The upload is in read(), but the event loop can still cancel it.
            task.cancel()
            with self.assertRaises(asyncio.CancelledError):
                await task
        finally:
            release.set()
        self.assertEqual(1, source.read.call_count)
        source.close.assert_not_called()

    async def test_download_error_and_early_close(self):
        self.server.files[('files', 'file')] = b'abc'
        self.server.download_error = grpc.StatusCode.UNAVAILABLE
        response = await self.client.get_binary_file_alpha1('files', 'file')
        self.assertEqual(b'abc', await response.__anext__())
        with self.assertRaises(DaprGrpcError) as caught:
            await response.read()
        self.assertEqual(grpc.StatusCode.UNAVAILABLE, caught.exception.code())
        self.server.download_error = None
        self.server.hold_download = True
        self.server.download_cancelled.clear()
        response = await self.client.get_binary_file_alpha1('files', 'file')
        async with response:
            self.assertEqual(b'abc', await response.read(3))
        self.assertTrue(await asyncio.to_thread(self.server.download_cancelled.wait, 5))

    async def test_deadline_ends_upload_while_file_read_is_blocked(self):
        entered = threading.Event()
        release = threading.Event()
        source = MagicMock()

        def read(size):
            entered.set()
            release.wait(5)
            return b'x'

        source.read.side_effect = read
        try:
            with self.assertRaises(DaprGrpcError) as caught:
                await asyncio.wait_for(
                    self.client.set_binary_file_alpha1('files', 'file', source, timeout=0.1),
                    timeout=2,
                )
            self.assertTrue(entered.is_set())
            self.assertEqual(grpc.StatusCode.DEADLINE_EXCEEDED, caught.exception.code())
        finally:
            release.set()
        self.assertEqual(1, source.read.call_count)
        source.close.assert_not_called()

    @patch.object(settings, 'DAPR_API_TOKEN', 'test-token')
    async def test_upload_deadline_leaves_no_request_tasks_with_interceptors(self):
        release = threading.Event()
        source = MagicMock()
        source.read.side_effect = lambda size: release.wait(5) and b'x'
        self.server.token = 'test-token'
        before = asyncio.all_tasks()
        try:
            async with DaprGrpcClientAsync(f'127.0.0.1:{self.server.grpc_port}') as client:
                with self.assertRaises(DaprGrpcError) as caught:
                    await client.set_binary_file_alpha1('files', 'file', source, timeout=0.1)
                self.assertEqual(grpc.StatusCode.DEADLINE_EXCEEDED, caught.exception.code())
                # Let scheduled cleanup finish, while keeping the client open:
                # closing the channel must not be needed to clean up each RPC.
                finishing = asyncio.all_tasks() - before
                if finishing:
                    await asyncio.wait(finishing, timeout=1)
                pending = [task for task in asyncio.all_tasks() - before if not task.done()]
                self.assertEqual([], [task.get_coro().__qualname__ for task in pending])
        finally:
            release.set()
        source.close.assert_not_called()

    async def test_slow_server_applies_backpressure_to_file_reader(self):
        self.server.hold_upload_body = True
        source = MagicMock()
        source.read.side_effect = [b'x' * 32768] * 4096 + [b'']
        task = asyncio.create_task(self.client.set_binary_file_alpha1('files', 'file', source))
        try:
            self.assertTrue(await asyncio.to_thread(self.server.upload_body_started.wait, 5))
            await asyncio.sleep(0.1)
            self.assertFalse(task.done())
            self.assertLess(source.read.call_count, 4096)
            task.cancel()
            with self.assertRaises(asyncio.CancelledError):
                await task
        finally:
            task.cancel()
            self.server.upload_body_release.set()
            await asyncio.gather(task, return_exceptions=True)
        source.close.assert_not_called()

    async def test_client_shutdown_cancels_download(self):
        self.server.files[('files', 'file')] = b'abc'
        self.server.hold_download = True
        response = await self.client.get_binary_file_alpha1('files', 'file')
        self.assertEqual(b'abc', await response.read(3))
        await self.client.close()
        with self.assertRaises(asyncio.CancelledError):
            await response.read()
        self.assertTrue(await asyncio.to_thread(self.server.download_cancelled.wait, 5))

    async def test_cancel_blocked_download_preserves_cancellation(self):
        self.server.files[('files', 'file')] = b'abc'
        self.server.hold_download = True
        response = await self.client.get_binary_file_alpha1('files', 'file')
        self.assertEqual(b'abc', await response.read(3))
        task = asyncio.create_task(response.read())
        await asyncio.sleep(0)
        task.cancel()
        with self.assertRaises(asyncio.CancelledError):
            await task
        self.assertTrue(await asyncio.to_thread(self.server.download_cancelled.wait, 5))

    async def test_invalid_input_and_timeout(self):
        for data in ['text', io.StringIO('text'), None]:
            with self.subTest(data=data), self.assertRaises(TypeError):
                await self.client.set_binary_file_alpha1('files', 'file', data)
        for method in [self.client.get_binary_file_alpha1, self.client.delete_binary_file_alpha1]:
            with self.assertRaises(ValueError):
                await method('files', '')
        self.server.wait_for_upload = True
        try:
            with self.assertRaises(DaprGrpcError) as caught:
                await self.client.set_binary_file_alpha1('files', 'file', b'x', timeout=0.05)
            self.assertEqual(grpc.StatusCode.DEADLINE_EXCEEDED, caught.exception.code())
        finally:
            self.server.upload_release.set()

    @patch.object(settings, 'DAPR_API_TOKEN', 'test-token')
    @patch.object(settings, 'DAPR_API_TIMEOUT_SECONDS', 7)
    async def test_authentication_for_binary_store_rpc_shapes_over_actual_aio_channel(self):
        self.server.token = 'test-token'
        async with DaprGrpcClientAsync(f'127.0.0.1:{self.server.grpc_port}') as client:
            await client.set_binary_file_alpha1('files', 'file', b'hello')
            response = await client.get_binary_file_alpha1('files', 'file')
            self.assertEqual(b'hello', await response.read())
            await client.delete_binary_file_alpha1('files', 'file', timeout=3)
        self.assertEqual(['set', 'get', 'delete'], [c[0] for c in self.server.calls])
        for method, metadata, deadline in self.server.calls:
            self.assertEqual(1, metadata.count(('dapr-api-token', 'test-token')))
            if method in ['set', 'get']:
                self.assertGreater(deadline, 5)
                self.assertLessEqual(deadline, 7.1)
            elif method == 'delete':
                self.assertLessEqual(deadline, 3.1)

    @patch.object(settings, 'DAPR_API_TOKEN', 'test-token')
    async def test_custom_metadata_survives_binary_store_rpc_shapes(self):
        self.server.token = 'test-token'
        metadata = (('custom-header', 'custom-value'),)
        async with DaprGrpcClientAsync(f'127.0.0.1:{self.server.grpc_port}') as client:
            await client._stub.SetBinaryFileAlpha1(
                iter(_BinaryFileUpload('files', 'metadata', b'x', False, 32768)),
                metadata=metadata,
            )
            response = client._stub.GetBinaryFileAlpha1(
                binary_v1.GetBinaryFileRequestAlpha1(component_name='files', file_name='metadata'),
                metadata=metadata,
            )
            self.assertEqual(1, len([chunk async for chunk in response]))
            await client._stub.DeleteBinaryFileAlpha1(
                binary_v1.DeleteBinaryFileRequestAlpha1(
                    component_name='files', file_name='metadata'
                ),
                metadata=metadata,
            )
        self.assertEqual(['set', 'get', 'delete'], [c[0] for c in self.server.calls])
        for _, headers, _ in self.server.calls:
            self.assertEqual(1, headers.count(('dapr-api-token', 'test-token')))
            self.assertIn(('custom-header', 'custom-value'), headers)
