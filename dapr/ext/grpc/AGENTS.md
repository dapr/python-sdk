# AGENTS.md — dapr.ext.grpc

The gRPC extension provides a **server-side callback framework** for Dapr applications. It enables Python apps to act as Dapr callback services using a decorator-based API, handling service invocation, pub/sub subscriptions, input bindings, job events, and health checks.

## Source layout

```
dapr/ext/grpc/
├── __init__.py                    # Public API exports
├── app.py                         # App class — main entry point
├── _servicer.py                   # _CallbackServicer — internal routing
├── _health_servicer.py            # _HealthCheckServicer
└── py.typed

tests/ext/grpc/
├── test_app.py                    # Decorator registration tests
├── test_servicier.py              # Routing, handlers, bulk events
├── test_health_servicer.py        # Health check tests
└── test_topic_event_response.py   # Response status tests
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

## Internal routing (`_servicer.py`)

`_CallbackServicer` implements `AppCallbackServicer` + `AppCallbackAlphaServicer` gRPC service interfaces. It maintains internal registries:

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

Test patterns:
- `test_app.py` — decorator registration, health check registration
- `test_servicier.py` — handler invocation with mock gRPC context, return type handling (str, bytes, proto, response object), topic subscriptions, bulk events, bindings, duplicate registration errors
- `test_health_servicer.py` — health check callback invocation, missing callback (UNIMPLEMENTED)
- `test_topic_event_response.py` — response creation from enum and string values

## Key details

- **Synchronous only**: Uses `grpc.server()` with `ThreadPoolExecutor(10)`. No async handler support.
- **Default port**: 3010 (from `dapr.conf.global_settings.GRPC_APP_PORT`)
- **Topic handler event type**: inferred from the handler annotation. Annotating the event parameter with `dapr.ext.grpc.SubscriptionMessage` — the same SDK-owned type the streaming subscription API (`DaprClient.subscribe`) delivers, with `metadata()` populated from the gRPC invocation metadata — delivers that type. Unannotated or otherwise-annotated handlers receive the DEPRECATED `cloudevents.sdk.event.v1.Event` and `subscribe()` emits a `DeprecationWarning` at registration. Deprecation timeline: 1.20 delivers `SubscriptionMessage` to unannotated handlers (legacy only via explicit `v1.Event` annotation), 1.21 drops `cloudevents` from the `grpc` extra (import becomes conditional), 1.22 removes the legacy path entirely (same release the `flask_dapr` shim goes away). New code must annotate with `SubscriptionMessage`. (Internally the choice is plumbed through `_CallbackServicer.register_topic(legacy_cloudevent=...)`.)
- **Duplicate registration**: Registering the same method/topic/binding name twice raises `ValueError`
- **Missing handlers**: Calling an unregistered method/topic/binding raises `NotImplementedError` (gRPC UNIMPLEMENTED)
