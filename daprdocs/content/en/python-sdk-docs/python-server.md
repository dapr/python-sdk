---
type: docs
title: "Getting started with the Dapr server Python SDK"
linkTitle: "Server"
weight: 20000
description: How to get up and running with the Dapr server Python SDK
---

The Dapr Python SDK provides a built in gRPC server extension module, `dapr.ext.grpc`, for creating Dapr services.

## Installation

You can download and install the Dapr gRPC server extension module with:

```bash
pip3 install dapr-ext-grpc
```

## Listen for service invocation requests

The `App` object can be used to create a server, and the `InvokeServiceReqest` and `InvokeServiceResponse` objects can be used to handle incoming requests.

A simple service that will listen and respond to requests will look like:

```python
from dapr.ext.grpc import App, InvokeServiceRequest, InvokeServiceResponse

app = App()

@app.method(name='my-method')
def mymethod(request: InvokeServiceRequest) -> InvokeServiceResponse:
    print(request.metadata, flush=True)
    print(request.text(), flush=True)

    return InvokeServiceResponse(b'INVOKE_RECEIVED', "text/plain; charset=UTF-8")

app.run(50051)
```

Save this to a file named `myapp.py` and run it with:

```bash
dapr run --app-id myapp --app-port 50051 python myapp.py
```
