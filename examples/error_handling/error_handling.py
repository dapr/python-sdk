
from dapr.clients import DaprClient
from dapr.clients.exceptions import DaprGrpcError

with DaprClient() as d:
    storeName = 'statestore'

    key = 'key||'
    value = 'value_1'

    # Wait for sidecar to be up within 5 seconds.
    d.wait(5)

    # Save single state.
    try:
        d.save_state(store_name=storeName, key=key, value=value)
    except DaprGrpcError as err:
        print(f'Status code: {err.code()}')
        print(f"Message: {err.message()}")
        print(f"Error code: {err.error_code()}")
        print(f"Error info(reason): {err.error_info.reason}")
        print(f"Resource info (resource type): {err.resource_info.resource_type}")
        print(f"Resource info (resource name): {err.resource_info.resource_name}")
        print(f"Bad request (field): {err.bad_request.field_violations[0].field}")
        print(f"Bad request (description): {err.bad_request.field_violations[0].description}")