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
        print(f'Status code: {err.code()}', flush=True)
        print(f'Message: {err.message()}', flush=True)
        print(f'Error code: {err.error_code()}', flush=True)
        if err.status_details() is not None:
            print(f'Error info(reason): {err.status_details().error_info["reason"]}', flush=True)
            print(
                f'Resource info (resource type): {err.status_details().resource_info["resource_type"]}',
                flush=True,
            )
            print(
                f'Resource info (resource name): {err.status_details().resource_info["resource_name"]}',
                flush=True,
            )
            print(
                f'Bad request (field): {err.status_details().bad_request["field_violations"][0]["field"]}',
                flush=True,
            )
            print(
                f'Bad request (description): {err.status_details().bad_request["field_violations"][0]["description"]}',
                flush=True,
            )
            print(f'JSON: {err.json()}', flush=True)
