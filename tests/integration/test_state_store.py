import grpc
import pytest

from dapr.clients.grpc._request import TransactionalStateOperation, TransactionOperationType
from dapr.clients.grpc._state import StateItem

STORE = 'statestore'


@pytest.fixture(scope='module')
def client(dapr_env):
    return dapr_env.start_sidecar(app_id='test-state')


class TestSaveAndGetState:
    def test_save_and_get(self, client):
        client.save_state(store_name=STORE, key='k1', value='v1')
        state = client.get_state(store_name=STORE, key='k1')
        assert state.data == b'v1'
        assert state.etag

    def test_save_with_wrong_etag_fails(self, client):
        client.save_state(store_name=STORE, key='etag-test', value='original')
        with pytest.raises(grpc.RpcError) as exc_info:
            client.save_state(store_name=STORE, key='etag-test', value='bad', etag='9999')
        assert exc_info.value.code() == grpc.StatusCode.ABORTED

    def test_get_missing_key_returns_empty(self, client):
        state = client.get_state(store_name=STORE, key='nonexistent-key')
        assert state.data == b''


class TestBulkState:
    def test_save_and_get_bulk(self, client):
        client.save_bulk_state(
            store_name=STORE,
            states=[
                StateItem(key='bulk-1', value='v1'),
                StateItem(key='bulk-2', value='v2'),
            ],
        )
        items = client.get_bulk_state(store_name=STORE, keys=['bulk-1', 'bulk-2']).items
        by_key = {i.key: i.data for i in items}
        assert by_key['bulk-1'] == b'v1'
        assert by_key['bulk-2'] == b'v2'

    def test_save_bulk_with_wrong_etag_fails(self, client):
        client.save_state(store_name=STORE, key='bulk-etag-1', value='original')
        with pytest.raises(grpc.RpcError) as exc_info:
            client.save_bulk_state(
                store_name=STORE,
                states=[StateItem(key='bulk-etag-1', value='updated', etag='9999')],
            )
        assert exc_info.value.code() == grpc.StatusCode.ABORTED


class TestStateTransactions:
    def test_transaction_upsert(self, client):
        client.save_state(store_name=STORE, key='tx-1', value='original')
        etag = client.get_state(store_name=STORE, key='tx-1').etag

        client.execute_state_transaction(
            store_name=STORE,
            operations=[
                TransactionalStateOperation(
                    operation_type=TransactionOperationType.upsert,
                    key='tx-1',
                    data='updated',
                    etag=etag,
                ),
                TransactionalStateOperation(key='tx-2', data='new'),
            ],
        )

        assert client.get_state(store_name=STORE, key='tx-1').data == b'updated'
        assert client.get_state(store_name=STORE, key='tx-2').data == b'new'

    def test_transaction_delete(self, client):
        client.save_state(store_name=STORE, key='tx-del-1', value='v1')
        client.save_state(store_name=STORE, key='tx-del-2', value='v2')

        client.execute_state_transaction(
            store_name=STORE,
            operations=[
                TransactionalStateOperation(
                    operation_type=TransactionOperationType.delete, key='tx-del-1'
                ),
                TransactionalStateOperation(
                    operation_type=TransactionOperationType.delete, key='tx-del-2'
                ),
            ],
        )

        assert client.get_state(store_name=STORE, key='tx-del-1').data == b''
        assert client.get_state(store_name=STORE, key='tx-del-2').data == b''


class TestDeleteState:
    def test_delete_single(self, client):
        client.save_state(store_name=STORE, key='del-1', value='v1')
        client.delete_state(store_name=STORE, key='del-1')
        assert client.get_state(store_name=STORE, key='del-1').data == b''
