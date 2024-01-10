from dapr.ext.grpc import App, InvokeMethodRequest

import proto.response_pb2 as response_messages

app = App()


@app.method('my_method')
def mymethod(request: InvokeMethodRequest):
    print(request.metadata, flush=True)
    print(request.text(), flush=True)

    return response_messages.CustomResponse(
        isSuccess=True, code=200, message='Hello World - Success!'
    )


app.run(50051)
