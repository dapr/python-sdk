import pytest
from naming_utils import unique_name

from dapr.aio.clients import DaprClient as AsyncDaprClient
from dapr.clients.grpc._request import TransactionalStateOperation

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
