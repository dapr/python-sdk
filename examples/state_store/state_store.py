
"""
dapr run python3 state_store.py
"""

from dapr.clients import DaprClient

from dapr.clients.grpc._request import TransactionalStateOperation, TransactionOperationType

with DaprClient() as d:
    storeName = 'statestore'

    key = "key_1"
    value = "value_1"
    updated_value = "value_1_updated"

    another_key = "key_2"
    another_value = "value_2"

    # Save states.
    d.save_state(store_name=storeName, key=key, value=value)
    print(f"State store has successfully saved {value} with {key} as key")
    d.save_state(store_name=storeName, key=another_key, value=another_value)
    print(f"State store has successfully saved {another_value} with {another_key} as key")

    # Get one state by key.
    data = d.get_state(store_name=storeName, key=key).data
    print(f"Got value: {data}")

    # Transaction upsert
    d.execute_transaction(store_name=storeName, operations=[
        TransactionalStateOperation(
            operation_type=TransactionOperationType.upsert,
            key=key,
            data=updated_value),
        TransactionalStateOperation(key=another_key, data=another_value),
    ])

    # Batch get
    items = d.get_states(store_name=storeName, keys=[key, another_key]).items
    print(f"Got items: {[i.data for i in items]}")

    # Delete one state by key.
    d.delete_state(store_name=storeName, key=key)
    data = d.get_state(store_name=storeName, key=key).data
    print(f"Got value after delete: {data}")