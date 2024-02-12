"""
dapr run python3 state_store.py
"""

import grpc

from dapr.clients import DaprClient

from dapr.clients.grpc._request import TransactionalStateOperation, TransactionOperationType
from dapr.clients.grpc._state import StateItem


with DaprClient() as d:
    storeName = 'statestore'

    key = 'key_1'
    value = 'value_1'
    updated_value = 'value_1_updated'

    another_key = 'key_2'
    another_value = 'value_2'

    yet_another_key = 'key_3'
    yet_another_value = 'value_3'

    # Save single state.
    d.save_state(store_name=storeName, key=key, value=value)
    print(f'State store has successfully saved {value} with {key} as key')

    # Save with an etag that is different from the one stored in the database.
    try:
        d.save_state(store_name=storeName, key=key, value=another_value, etag='9999')
    except grpc.RpcError as err:
        # StatusCode should be StatusCode.ABORTED.
        print(f'Cannot save due to bad etag. ErrorCode={err.code()}')

        # For detailed error messages from the dapr runtime:
        # print(f"Details={err.details()})

    # Save multiple states.
    d.save_bulk_state(
        store_name=storeName,
        states=[
            StateItem(key=another_key, value=another_value),
            StateItem(key=yet_another_key, value=yet_another_value),
        ],
    )
    print(f'State store has successfully saved {another_value} with {another_key} as key')
    print(f'State store has successfully saved {yet_another_value} with {yet_another_key} as key')

    # Save bulk with etag that is different from the one stored in the database.
    try:
        d.save_bulk_state(
            store_name=storeName,
            states=[
                StateItem(key=another_key, value=another_value, etag='999'),
                StateItem(key=yet_another_key, value=yet_another_value, etag='999'),
            ],
        )
    except grpc.RpcError as err:
        # StatusCode should be StatusCode.ABORTED.
        print(f'Cannot save bulk due to bad etags. ErrorCode={err.code()}')

        # For detailed error messages from the dapr runtime:  # print(f"Details={err.details()})

    # Get one state by key.
    state = d.get_state(store_name=storeName, key=key, state_metadata={'metakey': 'metavalue'})
    print(f'Got value={state.data} eTag={state.etag}')

    # Transaction upsert
    d.execute_state_transaction(
        store_name=storeName,
        operations=[
            TransactionalStateOperation(
                operation_type=TransactionOperationType.upsert,
                key=key,
                data=updated_value,
                etag=state.etag,
            ),
            TransactionalStateOperation(key=another_key, data=another_value),
        ],
    )

    # Batch get
    items = d.get_bulk_state(
        store_name=storeName, keys=[key, another_key], states_metadata={'metakey': 'metavalue'}
    ).items
    print(f'Got items with etags: {[(i.data, i.etag) for i in items]}')

    # Delete one state by key.
    d.delete_state(store_name=storeName, key=key, state_metadata={'metakey': 'metavalue'})
    data = d.get_state(store_name=storeName, key=key).data
    print(f'Got value after delete: {data}')
