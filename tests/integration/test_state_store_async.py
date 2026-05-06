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

import pytest

from dapr.aio.clients import DaprClient as AsyncDaprClient
from dapr.clients.grpc._request import TransactionalStateOperation
from tests.naming_utils import unique_name

STORE = 'statestore'
GRPC_ADDRESS = '127.0.0.1:50001'


@pytest.fixture(scope='module')
def sidecar(dapr_env):
    dapr_env.start_sidecar(app_id='test-state-async')


async def test_save_and_get_round_trip(sidecar):
    key = unique_name(prefix='async-key-')
    value = b'async-value'

    async with AsyncDaprClient(address=GRPC_ADDRESS) as d:
        await d.save_state(store_name=STORE, key=key, value=value)
        resp = await d.get_state(store_name=STORE, key=key)

    assert resp.data == value


async def test_delete_state_removes_key(sidecar):
    key = unique_name(prefix='async-del-')

    async with AsyncDaprClient(address=GRPC_ADDRESS) as d:
        await d.save_state(store_name=STORE, key=key, value=b'bye')
        await d.delete_state(store_name=STORE, key=key)
        resp = await d.get_state(store_name=STORE, key=key)

    assert resp.data == b''


async def test_transaction_upsert_then_get(sidecar):
    key = unique_name(prefix='async-txn-')

    async with AsyncDaprClient(address=GRPC_ADDRESS) as d:
        await d.execute_state_transaction(
            store_name=STORE,
            operations=[TransactionalStateOperation(key=key, data=b'txn-value')],
        )
        resp = await d.get_state(store_name=STORE, key=key)

    assert resp.data == b'txn-value'
