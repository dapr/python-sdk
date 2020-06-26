from dapr import Dapr

with Dapr() as dapr:
    # Create a typed message with content type and body
    resp = dapr.invoke_service(
        id='invoke-receiver',
        method='my-method',
        data=b'INVOKE_RECEIVED',
        content_type='text/plain; charset=UTF-8',
    )

    # Print the response
    print(resp.content_type)
    print(resp.bytesdata)
