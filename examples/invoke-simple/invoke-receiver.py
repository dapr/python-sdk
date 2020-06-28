from dapr import App, CallbackResponse

app = App()

@app.method(name='my-method')
def mymethod(metadata, data, content_type, *http_args) -> CallbackResponse:
    print(metadata, flush=True)
    print(data, flush=True)

    return CallbackResponse(b'INVOKE_RECEIVED', "text/plain; charset=UTF-8")

app.daprize()

app.wait_until_stop()
