# Example - Invoke a service with an asyncio gRPC app

This example is the asyncio counterpart of [`invoke-simple`](../invoke-simple). It uses
`dapr.ext.grpc.aio.App`, which runs a `grpc.aio` server so handlers can be `async def` and are
awaited. The caller uses the async `dapr.aio.clients.DaprClient` to issue three invocations
concurrently.

The receiver sleeps for half a second inside the handler. Because the handlers are awaited on
one event loop rather than dispatched to a thread pool, all three invocations are served in
roughly that same half second.

> **Note:** Make sure to use the latest proto bindings

## Pre-requisites

- [Dapr CLI and initialized environment](https://docs.dapr.io/getting-started)
- [Install Python 3.10+](https://www.python.org/downloads/)

## Install Dapr python-SDK

<!-- Our CI/CD pipeline automatically installs the correct version, so we can skip this step in the automation -->

```bash
pip3 install "dapr[grpc]"
```

## Running in self-hosted mode

Run the following command in a terminal/command-prompt:

<!-- STEP
name: Run receiver
expected_stdout_lines:
  - '{"id": 1, "message": "hello world"}'
  - '{"id": 2, "message": "hello world"}'
  - '{"id": 3, "message": "hello world"}'
output_match_mode: substring
match_order: none
background: true
sleep: 5
-->

```bash
# 1. Start Receiver (expose gRPC server receiver on port 13551)
dapr run --app-id invoke-receiver --app-protocol grpc --app-port 13551 -- python3 invoke-receiver.py
```

<!-- END_STEP -->

In another terminal/command prompt run:

<!-- STEP
name: Run caller
expected_stdout_lines:
  - 'text/plain'
  - 'INVOKE_RECEIVED'
  - 'text/plain'
  - 'INVOKE_RECEIVED'
  - 'text/plain'
  - 'INVOKE_RECEIVED'
output_match_mode: substring
-->

```bash
# 2. Start Caller (runs three concurrent invocations, then exits)
dapr run --app-id invoke-caller --app-protocol grpc -- python3 invoke-caller.py
```

<!-- END_STEP -->

## Cleanup

<!-- STEP
expected_stdout_lines:
  - '✅  app stopped successfully: invoke-receiver'
name: Shutdown dapr
-->

```bash
dapr stop --app-id invoke-receiver
```

<!-- END_STEP -->

## The difference from `invoke-simple`

Only the import and the way the app is started change:

```diff
-from dapr.ext.grpc import App, InvokeMethodRequest, InvokeMethodResponse
+from dapr.ext.grpc.aio import App, InvokeMethodRequest, InvokeMethodResponse

 app = App()

 @app.method(name='my-method')
-def mymethod(request: InvokeMethodRequest) -> InvokeMethodResponse:
+async def mymethod(request: InvokeMethodRequest) -> InvokeMethodResponse:
     ...

-app.run(13551)
+asyncio.run(app.run(13551))
```

`App.run()` and `App.stop()` are coroutines on the asyncio app. Everything else — `@app.method`,
`@app.subscribe`, `@app.binding`, `@app.job_event`, `register_health_check` and
`add_external_service` — take the same arguments as on the synchronous app. The decorators
return the handler, so the decorated name stays bound (the synchronous decorators return
`None`), and may be called at any time. `add_external_service` is the one exception: it must
be called before the app is started.
