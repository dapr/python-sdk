
"""
dapr run --app-protocol grpc --dapr-grpc-port=50001 python example.py
"""

from dapr.clients import DaprClient

with DaprClient() as d:
    key = "key_1"
    storeName = 'statestore'
    value = "value_1"

    d.save_state(store_name=storeName, key=key, value=value)
    print(f"State store has successfully saved {value} with {key} as key")
    data = d.get_state(store_name=storeName, key=key).data
    print(f"Got value: {data}")
    d.delete_state(store_name=storeName, key=key)
    data = d.get_state(store_name=storeName, key=key).data
    print(f"Got value: {data}")