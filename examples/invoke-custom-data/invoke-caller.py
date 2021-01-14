from dapr.clients import DaprClient

import proto.response_pb2 as response_messages

with DaprClient() as d:
    # Create a typed message with content type and body
    resp = d.invoke_method(
        app_id='invoke-receiver',
        method_name='my_method',
        data=b'SOME_DATA',
        content_type='text/plain; charset=UTF-8',
    )

    res = response_messages.CustomResponse()
    resp.unpack(res)

    # Print Result
    print(res, flush=True)
