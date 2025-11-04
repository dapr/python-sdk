import json

from dapr.clients import DaprClient
from dapr.clients.exceptions import DaprHttpError

with DaprClient() as d:
    req_data = {'id': 1, 'message': 'hello world'}

    # First message: success
    # Create a typed message with content type and body
    resp1 = d.invoke_method(
        'invoke-receiver',
        'my-method',
        http_verb='POST',
        data=json.dumps(req_data),
    )

    # Print the response
    print(resp1.content_type, flush=True)
    print(resp1.text(), flush=True)
    print(str(resp1.status_code), flush=True)

    # Second message: error
    req_data = {'id': 2, 'message': 'hello world'}
    try:
        resp2 = d.invoke_method(
            'invoke-receiver',
            'my-method-err',
            http_verb='POST',
            data=json.dumps(req_data),
        )
    except DaprHttpError as e:
        print(e.message, flush=True)
        print(e.error_code, flush=True)
        print(e.raw_response_bytes, flush=True)
        print(str(e.status_code), flush=True)
        print(e.reason, flush=True)
