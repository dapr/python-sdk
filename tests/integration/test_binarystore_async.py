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
import hashlib
import io
import warnings

import grpc
import pytest

from dapr.aio.clients import DaprClient
from dapr.clients.exceptions import DaprGrpcError
from tests.binarystore_utils import EndOfUploadReader

pytestmark = [
    pytest.mark.binary_store,
    pytest.mark.filterwarnings('ignore:The Binary Store API:UserWarning'),
]


@pytest.mark.parametrize('size', [0, 1, 32767, 32768, 32769, 98309, 5 * 1024 * 1024])
async def test_streaming_round_trip(binary_store_endpoint, size):
    name = f'async/round-trip-{size}'
    data = (bytes(range(256)) * (size // 256 + 1))[:size]
    async with DaprClient(address=binary_store_endpoint) as client:
        source = io.BytesIO(data)
        await client.set_binary_file_alpha1('binarystore', name, source)
        assert not source.closed
        digest = hashlib.sha256()
        response = await client.get_binary_file_alpha1('binarystore', name)
        async with response:
            digest.update(await response.read(7))
            async for chunk in response:
                digest.update(chunk)
        assert digest.digest() == hashlib.sha256(data).digest()
        await client.delete_binary_file_alpha1('binarystore', name)
        with pytest.raises(DaprGrpcError) as caught:
            response = await client.get_binary_file_alpha1('binarystore', name)
            await response.read()
        assert caught.value.code() == grpc.StatusCode.NOT_FOUND


async def test_overwrite_errors_and_early_close(binary_store_endpoint):
    async with DaprClient(address=binary_store_endpoint) as client:
        await client.set_binary_file_alpha1('binarystore', 'async/overwrite', b'original')
        with pytest.raises(DaprGrpcError) as caught:
            await client.set_binary_file_alpha1('binarystore', 'async/overwrite', b'rejected')
        assert caught.value.code() == grpc.StatusCode.ALREADY_EXISTS
        await client.set_binary_file_alpha1(
            'binarystore', 'async/overwrite', b'x' * 100000, overwrite=True
        )
        response = await client.get_binary_file_alpha1('binarystore', 'async/overwrite')
        async with response:
            assert await response.read(1) == b'x'
        await client.delete_binary_file_alpha1('binarystore', 'async/overwrite')
        with pytest.raises(DaprGrpcError) as caught:
            await client.delete_binary_file_alpha1('binarystore', 'async/overwrite')
        assert caught.value.code() == grpc.StatusCode.NOT_FOUND
        with pytest.raises(DaprGrpcError) as caught:
            await client.set_binary_file_alpha1('limited', 'too-big', b'x' * 65)
        assert caught.value.code() == grpc.StatusCode.RESOURCE_EXHAUSTED
        with pytest.raises(DaprGrpcError) as caught:
            await client.set_binary_file_alpha1('missing', 'file', b'')
        assert caught.value.code() == grpc.StatusCode.INVALID_ARGUMENT
        with pytest.raises(DaprGrpcError) as caught:
            response = await client.get_binary_file_alpha1('missing', 'file')
            await response.read()
        assert caught.value.code() == grpc.StatusCode.INVALID_ARGUMENT


async def test_capacity_recovery_and_failed_overwrite_preserves_original(binary_store_endpoint):
    async with DaprClient(address=binary_store_endpoint) as client:
        await client.set_binary_file_alpha1('limited', 'capacity-a', b'a' * 64)
        await client.set_binary_file_alpha1('limited', 'capacity-b', b'b' * 64)
        with pytest.raises(DaprGrpcError) as caught:
            await client.set_binary_file_alpha1('limited', 'overflow', b'x')
        assert caught.value.code() == grpc.StatusCode.RESOURCE_EXHAUSTED
        with pytest.raises(DaprGrpcError) as caught:
            await client.set_binary_file_alpha1('limited', 'capacity-a', b'c' * 65, overwrite=True)
        assert caught.value.code() == grpc.StatusCode.RESOURCE_EXHAUSTED
        response = await client.get_binary_file_alpha1('limited', 'capacity-a')
        async with response:
            assert await response.read() == b'a' * 64
        with pytest.raises(DaprGrpcError) as caught:
            response = await client.get_binary_file_alpha1('limited', 'overflow')
            await response.read()
        assert caught.value.code() == grpc.StatusCode.NOT_FOUND
        await client.delete_binary_file_alpha1('limited', 'capacity-b')
        await client.set_binary_file_alpha1('limited', 'capacity-c', b'c' * 64)
        await client.delete_binary_file_alpha1('limited', 'capacity-a')
        await client.delete_binary_file_alpha1('limited', 'capacity-c')


async def test_concurrent_calls_on_shared_client(binary_store_endpoint):
    async with DaprClient(address=binary_store_endpoint) as client:

        async def round_trip(index):
            name = f'concurrent/{index}'
            data = bytes([index]) * (256 * 1024 + index)
            await client.set_binary_file_alpha1('binarystore', name, data)
            response = await client.get_binary_file_alpha1('binarystore', name)
            async with response:
                assert await response.read() == data
            await client.delete_binary_file_alpha1('binarystore', name)

        await asyncio.gather(*(round_trip(index) for index in range(4)))


@pytest.mark.parametrize('overwrite', [False, True])
async def test_incomplete_upload_is_not_published(binary_store_endpoint, overwrite):
    async with DaprClient(address=binary_store_endpoint) as client:
        name = f'pending/{overwrite}'
        if overwrite:
            await client.set_binary_file_alpha1('binarystore', name, b'original')
        with EndOfUploadReader(b'x' * 128000) as source:
            upload = asyncio.create_task(
                client.set_binary_file_alpha1('binarystore', name, source, overwrite=overwrite)
            )
            try:
                assert await asyncio.to_thread(source.ready.wait, 5)
                assert not upload.done()
                if overwrite:
                    response = await client.get_binary_file_alpha1('binarystore', name)
                    async with response:
                        assert await response.read() == b'original'
                else:
                    with pytest.raises(DaprGrpcError) as caught:
                        response = await client.get_binary_file_alpha1('binarystore', name)
                        await response.read()
                    assert caught.value.code() == grpc.StatusCode.NOT_FOUND
            finally:
                source.release.set()
                await asyncio.wait_for(upload, timeout=5)
            assert not source.closed
        response = await client.get_binary_file_alpha1('binarystore', name)
        async with response:
            assert await response.read() == b'x' * 128000
        await client.delete_binary_file_alpha1('binarystore', name)


async def test_large_duplicate_rejections_preserve_original(binary_store_endpoint):
    async with DaprClient(address=binary_store_endpoint) as client:
        await client.set_binary_file_alpha1('binarystore', 'duplicate', b'original')
        masked_statuses = 0
        for _ in range(8):
            with io.BytesIO(b'x' * (1024 * 1024)) as source:
                with pytest.raises(DaprGrpcError) as caught:
                    await client.set_binary_file_alpha1(
                        'binarystore', 'duplicate', source, chunk_size=1024
                    )
                if caught.value.code() == grpc.StatusCode.INTERNAL:
                    # grpc/grpc#36066 can overwrite the server's rejection in
                    # Core. Accept only that precise transport failure, keeping
                    # the SDK's error wrapper/cause and data safety under test.
                    cause = caught.value.__cause__
                    assert isinstance(cause, grpc.aio.AioRpcError)
                    assert caught.value.details() == 'Internal error from Core'
                    assert 'execute_batch' in cause.debug_error_string()
                    masked_statuses += 1
                else:
                    assert caught.value.code() == grpc.StatusCode.ALREADY_EXISTS
                assert not source.closed
        response = await client.get_binary_file_alpha1('binarystore', 'duplicate')
        async with response:
            assert await response.read() == b'original'
        await client.delete_binary_file_alpha1('binarystore', 'duplicate')
        if masked_statuses:
            warnings.warn(
                f'grpc/grpc#36066 masked ALREADY_EXISTS as INTERNAL in '
                f'{masked_statuses}/8 early upload rejections; original data was preserved',
                RuntimeWarning,
                stacklevel=1,
            )
