from dapr import Dapr

with Dapr() as d:
    # Create a typed message with content type and body
    resp = d.invoke_service(
        id='invoke-receiver',
        method='my-method',
        data=b'INVOKE_RECEIVED',
        content_type='text/plain; charset=UTF-8',
    )

    # Print the response
    print(resp.content_type, flush=True)
    print(resp.bytesdata, flush=True)
