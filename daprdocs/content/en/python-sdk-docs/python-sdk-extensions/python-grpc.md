---
type: docs
title: "Getting started with the Dapr Python gRPC service extension"
linkTitle: "gRPC"
weight: 20000
description: How to get up and running with the Dapr Python gRPC extension package
---

The Dapr Python SDK provides a built in gRPC server extension module, `dapr.ext.grpc`, for creating Dapr services.

## Installation

You can download and install the Dapr gRPC server extension module with:

{{< tabs Stable Development>}}

{{% codetab %}}
```bash
pip install dapr-ext-grpc
```
{{% /codetab %}}

{{% codetab %}}
{{% alert title="Note" color="warning" %}}
The development package will contain features and behavior that will be compatible with the pre-release version of the Dapr runtime. Make sure to uninstall any stable versions of the Python SDK extension before installing the dapr-dev package.
{{% /alert %}}

```bash
pip3 install dapr-ext-grpc-dev
```
{{% /codetab %}}

{{< /tabs >}}

## Examples

The `App` object can be used to create a server.

### Listen for service invocation requests

The `InvokeMethodReqest` and `InvokeMethodResponse` objects can be used to handle incoming requests.

A simple service that will listen and respond to requests will look like:

```python
from dapr.ext.grpc import App, InvokeMethodRequest, InvokeMethodResponse

app = App()

@app.method(name='my-method')
def mymethod(request: InvokeMethodRequest) -> InvokeMethodResponse:
    print(request.metadata, flush=True)
    print(request.text(), flush=True)

    return InvokeMethodResponse(b'INVOKE_RECEIVED', "text/plain; charset=UTF-8")

app.run(50051)
```

A full sample can be found [here](https://github.com/dapr/python-sdk/tree/v1.0.0rc2/examples/invoke-simple).

### Subscribe to a topic

```python
from cloudevents.sdk.event import v1
from dapr.ext.grpc import App

app = App()

@app.subscribe(pubsub_name='pubsub', topic='TOPIC_A')
def mytopic(event: v1.Event) -> None:
    print(event.Data(),flush=True)

app.run(50051)
```

A full sample can be found [here](https://github.com/dapr/python-sdk/blob/v1.0.0rc2/examples/pubsub-simple/subscriber.py).

### Setup input binding trigger

```python
from dapr.ext.grpc import App, BindingRequest

app = App()

@app.binding('kafkaBinding')
def binding(request: BindingRequest):
    print(request.text(), flush=True)

app.run(50051)
```

A full sample can be found [here](https://github.com/dapr/python-sdk/tree/v1.0.0rc2/examples/invoke-binding).

## Related links
- [PyPi](https://pypi.org/project/dapr-ext-grpc/)