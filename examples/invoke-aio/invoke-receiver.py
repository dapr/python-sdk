import asyncio
from dapr.ext.grpc.aio import App, InvokeMethodRequest, InvokeMethodResponse

app = App()


@app.method(name='my-method')
async def mymethod(request: InvokeMethodRequest) -> InvokeMethodResponse:
    print(request.metadata, flush=True)
    print(request.text(), flush=True)

    return InvokeMethodResponse(b'INVOKE_RECEIVED', 'text/plain; charset=UTF-8')


asyncio.run(app.run(50051))
