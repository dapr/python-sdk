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

from tests.naming_utils import unique_name

BINDING = 'localbinding'
BINDING_ROOT = Path(__file__).resolve().parent / '.binding-data'


@pytest.fixture(scope='module')
def client(dapr_env):
    return dapr_env.start_sidecar(app_id='test-invoke-binding')


def test_create_writes_file_to_disk(client):
    file_name = unique_name(prefix='binding-', suffix='.txt')
    payload = b'hello from sync invoke_binding'

    client.invoke_binding(
        binding_name=BINDING,
        operation='create',
        data=payload,
        binding_metadata={'fileName': file_name},
    )

    assert (BINDING_ROOT / file_name).read_bytes() == payload


def test_create_then_get_round_trip(client):
    file_name = unique_name(prefix='binding-', suffix='.txt')
    payload = b'sync round-trip payload'

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


def test_create_with_string_payload(client):
    file_name = unique_name(prefix='binding-', suffix='.txt')
    payload = 'sync string payload'

    client.invoke_binding(
        binding_name=BINDING,
        operation='create',
        data=payload,
        binding_metadata={'fileName': file_name},
    )

    assert (BINDING_ROOT / file_name).read_text() == payload


def test_delete_removes_file(client):
    file_name = unique_name(prefix='binding-', suffix='.txt')
    file_path = BINDING_ROOT / file_name

    client.invoke_binding(
        binding_name=BINDING,
        operation='create',
        data=b'to be deleted',
        binding_metadata={'fileName': file_name},
    )
    assert file_path.exists()

    client.invoke_binding(
        binding_name=BINDING,
        operation='delete',
        binding_metadata={'fileName': file_name},
    )
    assert not file_path.exists()


def test_list_includes_created_file(client):
    file_name = unique_name(prefix='binding-', suffix='.txt')
    client.invoke_binding(
        binding_name=BINDING,
        operation='create',
        data=b'listed',
        binding_metadata={'fileName': file_name},
    )

    response = client.invoke_binding(binding_name=BINDING, operation='list')
    assert file_name in response.data.decode()
