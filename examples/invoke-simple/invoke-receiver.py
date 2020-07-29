from dapr.ext.grpc import App, InvokeServiceRequest, InvokeServiceResponse

app = App()

@app.method(name='my-method')
def mymethod(request: InvokeServiceRequest) -> InvokeServiceResponse:
    print(request.metadata, flush=True)
    print(request.text(), flush=True)

    return InvokeServiceResponse(b'INVOKE_RECEIVED', "text/plain; charset=UTF-8")

app.run(50051)
