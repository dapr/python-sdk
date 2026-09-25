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

from pathlib import Path

import pytest

from dapr.aio.clients import DaprClient as AsyncDaprClient
from tests.naming_utils import unique_name

BINDING = 'localbinding'
BINDING_ROOT = Path(__file__).resolve().parent / '.binding-data'
GRPC_ADDRESS = '127.0.0.1:13501'


@pytest.fixture(scope='module')
def sidecar(dapr_env):
    dapr_env.start_sidecar(app_id='test-invoke-binding-async')


async def test_create_writes_file_to_disk(sidecar):
    file_name = unique_name(prefix='binding-', suffix='.txt')
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
    file_name = unique_name(prefix='binding-', suffix='.txt')
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
