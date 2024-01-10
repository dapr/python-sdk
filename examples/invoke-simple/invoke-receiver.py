from dapr.ext.grpc import App, InvokeMethodRequest, InvokeMethodResponse

app = App()


@app.method(name='my-method')
def mymethod(request: InvokeMethodRequest) -> InvokeMethodResponse:
    print(request.metadata, flush=True)
    print(request.text(), flush=True)

    return InvokeMethodResponse(b'INVOKE_RECEIVED', 'text/plain; charset=UTF-8')


app.run(50051)
