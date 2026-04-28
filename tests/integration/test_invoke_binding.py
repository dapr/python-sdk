import json
import uuid
from pathlib import Path

import grpc
import pytest

BINDING = 'localbinding'
BINDING_ROOT = Path(__file__).resolve().parent / '.binding-data'


@pytest.fixture(scope='module')
def client(dapr_env):
    return dapr_env.start_sidecar(app_id='test-invoke-binding')


def _unique_file() -> str:
    return f'binding-{uuid.uuid4().hex[:8]}.txt'


def test_create_writes_file_to_disk(client):
    file_name = _unique_file()
    payload = b'hello from invoke_binding'

    client.invoke_binding(
        binding_name=BINDING,
        operation='create',
        data=payload,
        binding_metadata={'fileName': file_name},
    )

    assert (BINDING_ROOT / file_name).read_bytes() == payload


def test_get_reads_file_from_disk(client):
    file_name = _unique_file()
    payload = json.dumps({'id': 1, 'message': 'hello'}).encode()
    (BINDING_ROOT / file_name).write_bytes(payload)

    response = client.invoke_binding(
        binding_name=BINDING,
        operation='get',
        binding_metadata={'fileName': file_name},
    )

    assert response.data == payload


def test_create_then_get_round_trip(client):
    file_name = _unique_file()
    payload = b'round-trip payload'

    client.invoke_binding(
        binding_name=BINDING,
        operation='create',
        data=payload,
        binding_metadata={'fileName': file_name},
    )
    response = client.invoke_binding(
        binding_name=BINDING,
        operation='get',
        binding_metadata={'fileName': file_name},
    )

    assert response.data == payload


def test_delete_removes_file(client):
    file_name = _unique_file()
    target_file = BINDING_ROOT / file_name
    target_file.write_bytes(b'to be deleted')

    client.invoke_binding(
        binding_name=BINDING,
        operation='delete',
        binding_metadata={'fileName': file_name},
    )

    assert not target_file.exists()


def test_unknown_binding_raises(client):
    with pytest.raises(grpc.RpcError):
        client.invoke_binding(
            binding_name='does-not-exist',
            operation='create',
            data=b'x',
            binding_metadata={'fileName': _unique_file()},
        )


def test_unknown_operation_raises(client):
    with pytest.raises(grpc.RpcError):
        client.invoke_binding(
            binding_name=BINDING,
            operation='bogus-op',
            data=b'x',
            binding_metadata={'fileName': _unique_file()},
        )
