import uuid
from pathlib import Path

import pytest

from dapr.aio.clients import DaprClient as AsyncDaprClient

BINDING = 'localbinding'
BINDING_ROOT = Path(__file__).resolve().parent / '.binding-data'
GRPC_ADDRESS = '127.0.0.1:50001'


@pytest.fixture(scope='module')
def sidecar(dapr_env):
    dapr_env.start_sidecar(app_id='test-invoke-binding-async')


async def test_create_writes_file_to_disk(sidecar):
    file_name = f'binding-{uuid.uuid4().hex[:8]}.txt'
    payload = b'hello from async invoke_binding'

    async with AsyncDaprClient(address=GRPC_ADDRESS) as d:
        await d.invoke_binding(
            binding_name=BINDING,
            operation='create',
            data=payload,
            binding_metadata={'fileName': file_name},
        )

    assert (BINDING_ROOT / file_name).read_bytes() == payload


async def test_create_then_get_round_trip(sidecar):
    file_name = f'binding-{uuid.uuid4().hex[:8]}.txt'
    payload = b'async round-trip payload'

    async with AsyncDaprClient(address=GRPC_ADDRESS) as d:
        await d.invoke_binding(
            binding_name=BINDING,
            operation='create',
            data=payload,
            binding_metadata={'fileName': file_name},
        )
        response = await d.invoke_binding(
            binding_name=BINDING,
            operation='get',
            binding_metadata={'fileName': file_name},
        )

    assert response.data == payload
