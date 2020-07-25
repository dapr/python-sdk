from dapr.ext.grpc import App, BindingRequest

app = App(50051)

@app.binding('kafkaBinding')
def binding(request: BindingRequest):
    print(request.text(), flush=True)

app.run()