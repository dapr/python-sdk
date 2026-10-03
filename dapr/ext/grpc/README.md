# dapr.ext.grpc

gRPC AppCallback server framework for Dapr Python SDK applications. Provides
decorator-based registration for service invocation, pub/sub, bindings, jobs,
and health checks.

```sh
pip install "dapr[grpc]"
```

```python
from dapr.ext.grpc import App
```

An asyncio-native app backed by a `grpc.aio` server is available under
`dapr.ext.grpc.aio`. It exposes the same names and decorators; handlers may be
`async def` and are awaited, and `run()`/`stop()` are coroutines:

```python
import asyncio

from dapr.ext.grpc.aio import App, InvokeMethodRequest, InvokeMethodResponse

app = App()


@app.method(name='my-method')
async def my_method(request: InvokeMethodRequest) -> InvokeMethodResponse:
    ...


asyncio.run(app.run(50051))
```

Plain (non-async) handlers are still accepted, but they run inline on the event
loop, so they must not block. See the [`invoke-simple-async`][invoke-async] and
[`pubsub-simple-async`][pubsub-async] examples.

See the root [README](../../../README.md) for migration steps from the legacy
`dapr-ext-grpc` distribution.

[invoke-async]: ../../../examples/invoke-simple-async
[pubsub-async]: ../../../examples/pubsub-simple-async
