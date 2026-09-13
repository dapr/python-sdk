# AGENTS.md — dapr.ext.grpc

The gRPC extension provides a **server-side callback framework** for Dapr applications. It enables Python apps to act as Dapr callback services using a decorator-based API, handling service invocation, pub/sub subscriptions, input bindings, job events, and health checks.

## Source layout

```
dapr/ext/grpc/
├── __init__.py                    # Public API exports
├── app.py                         # App class — main entry point (sync)
├── _servicer.py                   # _CallbackServicerBase (shared) + _CallbackServicer (sync)
├── _health_servicer.py            # _HealthCheckServicerBase (shared) + _HealthCheckServicer
├── aio/                           # asyncio-native variant, same public surface
│   ├── __init__.py                #   Public API exports
│   ├── app.py                     #   App class backed by grpc.aio
│   ├── _servicer.py               #   _AioCallbackServicer — async gRPC entry points
│   └── _health_servicer.py        #   _AioHealthCheckServicer
└── py.typed

tests/ext/grpc/
├── test_app.py                    # Decorator registration tests
├── test_servicer.py               # Routing, handlers, bulk events
├── test_health_servicer.py        # Health check tests
├── test_topic_event_response.py   # Response status tests
└── aio/
    ├── test_app.py                # Decorator registration, lazy server creation, lifecycle
    ├── test_servicer.py           # Async handlers, sync/aio parity guards
    ├── test_health_servicer.py    # Async and sync health check callbacks
    └── test_server.py             # End-to-end over a real grpc.aio server
```

Installed via the `grpc` extra on core dapr: `pip install "dapr[grpc]"`.

## Public API

```python
from dapr.ext.grpc import (
    App,                    # Main entry point — decorator-based gRPC server
    Rule,                   # CEL-based topic rule with priority
    SubscriptionMessage,    # Event type received by pub/sub topic handlers (preferred)
    InvokeMethodRequest,    # Request object for service invocation handlers
    InvokeMethodResponse,   # Response object for service invocation handlers
    BindingRequest,         # Request object for input binding handlers
    TopicEventResponse,     # Response object for pub/sub handlers
    Job,                    # Job definition for scheduler
    JobEvent,               # Job event received by handler
    FailurePolicy,          # ABC for job failure policies
    DropFailurePolicy,      # Drop on failure (no retry)
    ConstantFailurePolicy,  # Retry with constant interval
)
```

Note: `InvokeMethodRequest`, `InvokeMethodResponse`, `BindingRequest`, `TopicEventResponse`, `Job`, `JobEvent`, and failure policies are actually defined in the core SDK (`dapr/clients/grpc/`) and re-exported here.

`dapr.ext.grpc.aio` exports the same names. Swapping the import is the only change an app needs, beyond `async def` handlers and awaiting `run()`/`stop()`.

## App class (`app.py`)

The central entry point. Creates a gRPC server and provides decorators for handler registration.

### Decorators

```python
app = App()

@app.method('method_name')
def handle_method(request: InvokeMethodRequest) -> InvokeMethodResponse:
    ...

@app.subscribe(pubsub_name='pubsub', topic='orders', metadata={}, dead_letter_topic=None,
                rule=Rule('event.type == "order"', priority=1), disable_topic_validation=False)
def handle_event(event: SubscriptionMessage) -> Optional[TopicEventResponse]:
    ...

@app.binding('binding_name')
def handle_binding(request: BindingRequest) -> None:
    ...

@app.job_event('job_name')
def handle_job(event: JobEvent) -> None:
    ...

app.register_health_check(lambda: None)  # Not a decorator — direct registration
```

### Lifecycle

- `app.run(app_port=3010, listen_address='[::]')` — starts gRPC server and blocks
- `app.stop()` — gracefully shuts down
- `app.add_external_service(servicer_cb, external_servicer)` — add external gRPC services

### Handler return types

**Method handlers** can return:
- `str` or `bytes` → wrapped in `InvokeMethodResponse` with `application/json`
- `InvokeMethodResponse` → used directly
- Protobuf message → packed into `google.protobuf.Any`

**Topic handlers** can return:
- `TopicEventResponse('success'|'retry'|'drop')` → explicit status
- `None` → defaults to SUCCESS

## Asyncio app (`aio/`)

`dapr.ext.grpc.aio.App` is the asyncio counterpart, backed by `grpc.aio.server()`. Same decorators, same registration semantics, same wire behavior.

```python
import asyncio
from dapr.ext.grpc.aio import App

app = App()

@app.subscribe(pubsub_name='pubsub', topic='orders')
async def handle_event(event: SubscriptionMessage) -> TopicEventResponse:
    ...

asyncio.run(app.run(3010))
```

Differences from the synchronous `App`, all of them forced by the async runtime:

- **`run()` and `stop()` are coroutines.** `stop(grace=None)` takes a grace period (the sync `stop()` is always immediate). There is no `__del__` hook, because a coroutine cannot be awaited from one — `run()` instead stops the server in a `finally`, so a cancelled app does not leave its port bound.
- **`start()` exists** as a non-blocking alternative to `run()`, for serving the app alongside other work on the same loop (e.g. from an ASGI lifespan handler). `run()` is `start()` plus `wait_for_termination()`.
- **The server is built lazily**, on the first `run()`/`start()` call, not in `__init__`. `grpc.aio.server()` binds to whichever event loop is current when it is called, so building it in `__init__` would attach it to the wrong loop. `add_external_service()` therefore queues its registration and replays it when the server is created, and raises if called once the app is running.
- **`start()` and `stop()` are serialised** by an `asyncio.Lock`. grpc.aio segfaults if a `stop()` call is *concurrently in flight* with a `start()` call, so the two must never overlap; the lock also means a restart waits for an in-progress drain rather than binding a second server to the same port. (Stopping a server whose own `start()` has already unwound — the cleanup path in `_start`'s `except` — is sequential, not concurrent, and is safe. `stop()` on a server that never started returns cleanly; on one whose `start()` was *cancelled part-way* it raises `InvalidStateError`, which that path suppresses.)
- **The lock is built per running loop**, not in `__init__`: an `asyncio.Lock` binds to the loop of its first *contended* acquire, so one built at construction raises "bound to a different event loop" on a second `asyncio.run()` — and silently stops excluding anything before that, because the uncontended path returns before the loop check.
- **Decorators return the handler**, so the decorated name stays bound. The sync decorators return `None`.
- **Handlers may be plain functions.** Results are awaited only when awaitable, so `register_health_check(lambda: None)` still works. A plain handler runs inline on the event loop and must not block.

### Sharing with the sync implementation

`_CallbackServicerBase` (in `_servicer.py`) holds everything that does not invoke a user handler: the handler registries, topic routing, and the request→event translation. `_CallbackServicer` and `_AioCallbackServicer` are **siblings** on top of it — neither subclasses the other — and each supplies only the gRPC entry points.

This keeps the churn-prone routing logic (`_get_topic_callback`, `register_topic`, the bulk entry builders) in one place while leaving the two servicers free to differ where they must. `tests/ext/grpc/aio/test_servicer.py::AsyncParityTests` enforces the arrangement: every RPC the sync servicer implements must be mirrored on the aio servicer as a coroutine function, and the registration helpers must stay shared rather than be reimplemented.

`_HealthCheckServicerBase` splits the health servicer the same way: registration in the base, the gRPC entry point in each sibling.

## Internal routing (`_servicer.py`)

`_CallbackServicerBase` implements `AppCallbackServicer` + `AppCallbackAlphaServicer` gRPC service interfaces; `_CallbackServicer` adds the synchronous entry points. It maintains internal registries:

- `_invoke_method_map` — method name → handler
- `_topic_map` — topic key → handler
- `_binding_map` — binding name → handler
- `_job_event_map` — job name → handler

**Topic routing with rules**: Topics support multiple handlers with CEL-based rules and priorities. Rules are sorted by priority (lower = higher priority). Topic key format: `{pubsub_name}:{topic}:{path}`.

**Bulk event processing**: `OnBulkTopicEvent` processes multiple entries per request. Each entry can be raw bytes or a CloudEvent. Per-entry status tracking in the response. Handler exceptions return RETRY status for that entry.

## Request/response types (from core SDK)

**InvokeMethodRequest**: `data` (bytes), `content_type`, `metadata` (from gRPC context), `text()`, `is_proto()`, `unpack(message)`

**InvokeMethodResponse**: `data` (bytes), `content_type`, `headers`, `status_code`, `text()`, `json()`, `is_proto()`, `pack(val)`

**BindingRequest**: `data` (bytes), `binding_metadata` (dict), `metadata`, `text()`

**TopicEventResponse**: `status` property → `TopicEventResponseStatus` enum (success=0, retry=1, drop=2)

**JobEvent**: `name` (str), `data` (bytes), `get_data_as_string(encoding='utf-8')`

## Dependencies (declared via the `grpc` extra in the root `pyproject.toml`)

- `dapr` (core, same wheel as this extension)
- `cloudevents >= 1.0.0, < 2.0.0` (deprecated, only used for the legacy handler event type)

## Testing

```bash
uv run python -m unittest discover -v ./tests/ext/grpc
```

`unittest discover` covers the whole tree including `aio/` — `IsolatedAsyncioTestCase` and
`subTest` are both native unittest. pytest runs the same tests:

```bash
uv run pytest ./tests/ext/grpc
```

Test patterns:
- `test_app.py` — decorator registration, health check registration
- `test_servicer.py` — handler invocation with mock gRPC context, return type handling (str, bytes, proto, response object), topic subscriptions, bulk events, bindings, duplicate registration errors
- `test_health_servicer.py` — health check callback invocation, missing callback (UNIMPLEMENTED)
- `test_topic_event_response.py` — response creation from enum and string values

## Key details

- **Sync app threading**: `dapr.ext.grpc.App` uses `grpc.server()` with `ThreadPoolExecutor(10)`. For `async def` handlers use `dapr.ext.grpc.aio.App`, which serves on a `grpc.aio` event loop instead.
- **Default port**: 3010 (from `dapr.conf.global_settings.GRPC_APP_PORT`)
- **Topic handler event type**: inferred from the handler annotation. Annotating the event parameter with `dapr.ext.grpc.SubscriptionMessage` — the same SDK-owned type the streaming subscription API (`DaprClient.subscribe`) delivers, with `metadata()` populated from the gRPC invocation metadata — delivers that type. Unannotated or otherwise-annotated handlers receive the DEPRECATED `cloudevents.sdk.event.v1.Event` and `subscribe()` emits a `DeprecationWarning` at registration. Deprecation timeline: 1.20 delivers `SubscriptionMessage` to unannotated handlers (legacy only via explicit `v1.Event` annotation), 1.21 drops `cloudevents` from the `grpc` extra (import becomes conditional), 1.22 removes the legacy path entirely (same release the `flask_dapr` shim goes away). New code must annotate with `SubscriptionMessage`. (Internally the choice is plumbed through `_CallbackServicerBase.register_topic(legacy_cloudevent=...)`.)
- **Duplicate registration**: Registering the same method/topic/binding name twice raises `ValueError`
- **Missing handlers**: Calling an unregistered method/topic/binding raises `NotImplementedError` (gRPC UNIMPLEMENTED)
