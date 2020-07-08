import json

from dapr import DaprClient

with DaprClient() as d:
    req_data = {
        'id': 1,
        'message': 'hello world'
    }

    # Create a typed message with content type and body
    resp = d.invoke_service(
        'invoke-receiver',
        'my-method',
        data=json.dumps(req_data),
    )

    # Print the response
    print(resp.content_type, flush=True)
    print(resp.content, flush=True)
