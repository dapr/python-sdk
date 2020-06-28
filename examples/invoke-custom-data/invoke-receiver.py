from dapr import App, CallbackResponse

import proto.response_pb2 as response_messages

app = App()

@app.method(name='my_method')
def mymethod(metadata, data, content_type, *http_args) -> CallbackResponse:
    print(metadata, flush=True)
    print(data, flush=True)

    return response_messages.CustomResponse(
        isSuccess=True,
        code=200,
        message="Hello World - Success!")

app.daprize()

app.wait_until_stop()
