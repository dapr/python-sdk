"""gRPC method handler for invoke integration tests."""

from dapr.ext.grpc import App, InvokeMethodRequest, InvokeMethodResponse

app = App()


@app.method(name='my-method')
def my_method(request: InvokeMethodRequest) -> InvokeMethodResponse:
    return InvokeMethodResponse(b'INVOKE_RECEIVED', 'text/plain; charset=UTF-8')


app.run(50051)
