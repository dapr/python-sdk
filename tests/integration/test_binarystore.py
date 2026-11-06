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

import hashlib
import io
from concurrent.futures import ThreadPoolExecutor

import grpc
import pytest

from dapr.clients.exceptions import DaprGrpcError
from tests.binarystore_utils import EndOfUploadReader

pytestmark = [
    pytest.mark.binary_store,
    pytest.mark.filterwarnings('ignore:The Binary Store API:UserWarning'),
]


@pytest.mark.parametrize('size', [0, 1, 32767, 32768, 32769, 98309, 5 * 1024 * 1024])
def test_streaming_round_trip(binary_store_client, size):
    client = binary_store_client
    name = f'sync/round-trip-{size}'
    data = (bytes(range(256)) * (size // 256 + 1))[:size]
    source = io.BytesIO(data)
    client.set_binary_file_alpha1('binarystore', name, source)
    assert not source.closed
    digest = hashlib.sha256()
    with client.get_binary_file_alpha1('binarystore', name) as response:
        assert response.read(0) == b''
        digest.update(response.read(7))
        for chunk in response:
            digest.update(chunk)
    assert digest.digest() == hashlib.sha256(data).digest()
    client.delete_binary_file_alpha1('binarystore', name)
    with pytest.raises(DaprGrpcError) as caught:
        client.get_binary_file_alpha1('binarystore', name).read()
    assert caught.value.code() == grpc.StatusCode.NOT_FOUND


def test_overwrite_and_missing_resources(binary_store_client):
    client = binary_store_client
    client.set_binary_file_alpha1('binarystore', 'sync/overwrite', b'original')
    with pytest.raises(DaprGrpcError) as caught:
        client.set_binary_file_alpha1('binarystore', 'sync/overwrite', b'rejected')
    assert caught.value.code() == grpc.StatusCode.ALREADY_EXISTS
    client.set_binary_file_alpha1('binarystore', 'sync/overwrite', b'replaced', overwrite=True)
    with client.get_binary_file_alpha1('binarystore', 'sync/overwrite') as response:
        assert response.read() == b'replaced'
    client.delete_binary_file_alpha1('binarystore', 'sync/overwrite')
    with pytest.raises(DaprGrpcError) as caught:
        client.delete_binary_file_alpha1('binarystore', 'sync/overwrite')
    assert caught.value.code() == grpc.StatusCode.NOT_FOUND
    for method in [
        client.set_binary_file_alpha1,
        client.get_binary_file_alpha1,
        client.delete_binary_file_alpha1,
    ]:
        with pytest.raises(DaprGrpcError) as caught:
            if method == client.set_binary_file_alpha1:
                method('missing', 'file', b'')
            elif method == client.get_binary_file_alpha1:
                method('missing', 'file').read()
            else:
                method('missing', 'file')
        assert caught.value.code() == grpc.StatusCode.INVALID_ARGUMENT


def test_capacity_rejection_and_early_close(binary_store_client):
    client = binary_store_client
    with pytest.raises(DaprGrpcError) as caught:
        client.set_binary_file_alpha1('limited', 'too-big', b'x' * 65)
    assert caught.value.code() == grpc.StatusCode.RESOURCE_EXHAUSTED
    client.set_binary_file_alpha1('binarystore', 'sync/early', b'x' * 100000)
    with client.get_binary_file_alpha1('binarystore', 'sync/early') as response:
        assert response.read(1) == b'x'
    client.delete_binary_file_alpha1('binarystore', 'sync/early')


def test_capacity_recovery_and_failed_overwrite_preserves_original(binary_store_client):
    client = binary_store_client
    client.set_binary_file_alpha1('limited', 'capacity-a', b'a' * 64)
    client.set_binary_file_alpha1('limited', 'capacity-b', b'b' * 64)
    with pytest.raises(DaprGrpcError) as caught:
        client.set_binary_file_alpha1('limited', 'overflow', b'x')
    assert caught.value.code() == grpc.StatusCode.RESOURCE_EXHAUSTED
    with pytest.raises(DaprGrpcError) as caught:
        client.set_binary_file_alpha1('limited', 'capacity-a', b'c' * 65, overwrite=True)
    assert caught.value.code() == grpc.StatusCode.RESOURCE_EXHAUSTED
    with client.get_binary_file_alpha1('limited', 'capacity-a') as response:
        assert response.read() == b'a' * 64
    with pytest.raises(DaprGrpcError) as caught:
        client.get_binary_file_alpha1('limited', 'overflow').read()
    assert caught.value.code() == grpc.StatusCode.NOT_FOUND
    client.delete_binary_file_alpha1('limited', 'capacity-b')
    client.set_binary_file_alpha1('limited', 'capacity-c', b'c' * 64)
    client.delete_binary_file_alpha1('limited', 'capacity-a')
    client.delete_binary_file_alpha1('limited', 'capacity-c')


def test_concurrent_calls_on_shared_client(binary_store_client):
    client = binary_store_client

    def round_trip(index):
        name = f'concurrent/{index}'
        data = bytes([index]) * (256 * 1024 + index)
        client.set_binary_file_alpha1('binarystore', name, data)
        with client.get_binary_file_alpha1('binarystore', name) as response:
            assert response.read() == data
        client.delete_binary_file_alpha1('binarystore', name)

    with ThreadPoolExecutor(max_workers=4) as pool:
        list(pool.map(round_trip, range(4)))


@pytest.mark.parametrize('overwrite', [False, True])
def test_incomplete_upload_is_not_published(binary_store_client, overwrite):
    client = binary_store_client
    name = f'pending/{overwrite}'
    if overwrite:
        client.set_binary_file_alpha1('binarystore', name, b'original')
    with EndOfUploadReader(b'x' * 128000) as source, ThreadPoolExecutor(max_workers=1) as pool:
        upload = pool.submit(
            client.set_binary_file_alpha1, 'binarystore', name, source, overwrite=overwrite
        )
        try:
            assert source.ready.wait(5)
            assert not upload.done()
            if overwrite:
                with client.get_binary_file_alpha1('binarystore', name) as response:
                    assert response.read() == b'original'
            else:
                with pytest.raises(DaprGrpcError) as caught:
                    client.get_binary_file_alpha1('binarystore', name).read()
                assert caught.value.code() == grpc.StatusCode.NOT_FOUND
        finally:
            source.release.set()
            upload.result(timeout=5)
        assert not source.closed
    with client.get_binary_file_alpha1('binarystore', name) as response:
        assert response.read() == b'x' * 128000
    client.delete_binary_file_alpha1('binarystore', name)


def test_large_duplicate_rejections_preserve_original(binary_store_client):
    client = binary_store_client
    client.set_binary_file_alpha1('binarystore', 'duplicate', b'original')
    for _ in range(8):
        with io.BytesIO(b'x' * (1024 * 1024)) as source:
            with pytest.raises(DaprGrpcError) as caught:
                client.set_binary_file_alpha1('binarystore', 'duplicate', source, chunk_size=1024)
            assert caught.value.code() == grpc.StatusCode.ALREADY_EXISTS
            assert not source.closed
    with client.get_binary_file_alpha1('binarystore', 'duplicate') as response:
        assert response.read() == b'original'
    client.delete_binary_file_alpha1('binarystore', 'duplicate')
