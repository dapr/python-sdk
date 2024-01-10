from dapr.ext.grpc import App, BindingRequest

app = App()


@app.binding('kafkaBinding')
def binding(request: BindingRequest):
    print(request.text(), flush=True)


app.run(50051)
