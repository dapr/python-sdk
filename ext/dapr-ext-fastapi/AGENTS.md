# AGENTS.md — dapr-ext-fastapi

The FastAPI extension provides two integration classes for building Dapr applications with [FastAPI](https://fastapi.tiangolo.com/): `DaprApp` for pub/sub subscriptions and `DaprActor` for actor hosting.

## Source layout

```
ext/dapr-ext-fastapi/
├── setup.cfg                      # Deps: dapr, uvicorn, fastapi
├── setup.py
├── tests/
│   ├── test_app.py                # DaprApp pub/sub tests
│   └── test_dapractor.py          # DaprActor response wrapping + route tests
└── dapr/ext/fastapi/
    ├── __init__.py                # Exports: DaprApp, DaprActor
    ├── app.py                     # DaprApp — pub/sub subscription handler
    ├── actor.py                   # DaprActor — actor runtime HTTP adapter
    └── version.py
```

## Public API

```python
from dapr.ext.fastapi import DaprApp, DaprActor
```

### DaprApp (`app.py`)

Wraps a FastAPI instance to add Dapr pub/sub event handling.

```python
app = FastAPI()
dapr_app = DaprApp(app, router_tags=['PubSub'])  # router_tags optional, default ['PubSub']

@dapr_app.subscribe(pubsub='pubsub', topic='orders', route='/handle-order',
                     metadata={}, dead_letter_topic=None)
def handle_order(event_data):
    return {'status': 'ok'}
```

- Auto-registers `GET /dapr/subscribe` endpoint returning subscription metadata
- Each `@subscribe` registers a POST route on the FastAPI app
- If `route` is omitted, defaults to `/events/{pubsub}/{topic}`
- Subscription metadata format: `{"pubsubname", "topic", "route", "metadata", "deadLetterTopic"}`

### DaprActor (`actor.py`)

Integrates Dapr's actor runtime with FastAPI by registering HTTP endpoints.

```python
app = FastAPI()
dapr_actor = DaprActor(app, router_tags=['Actor'])  # router_tags optional, default ['Actor']

await dapr_actor.register_actor(MyActorClass)
```

Auto-registers six endpoints:
- `GET /healthz` — health check
- `GET /dapr/config` — actor configuration discovery
- `DELETE /actors/{type}/{id}` — deactivation
- `PUT /actors/{type}/{id}/method/{method}` — method invocation
- `PUT /actors/{type}/{id}/method/timer/{timer}` — timer callback
- `PUT /actors/{type}/{id}/method/remind/{reminder}` — reminder callback

Method invocation extracts `Dapr-Reentrancy-Id` header for reentrant actor calls. All actor operations delegate to `ActorRuntime` from the core SDK.

**Response wrapping** (`_wrap_response`): Converts handler results to HTTP responses:
- String → JSON `{"message": "..."}` with optional `errorCode` for errors
- Bytes → raw `Response` with specified media type
- Dict/object → JSON serialized

**Error handling**: Catches `DaprInternalError` and generic `Exception`, returns 500 with error details.

## Dependencies

- `dapr >= 1.17.0.dev`
- `fastapi >= 0.60.1`
- `uvicorn >= 0.11.6`

## Testing

```bash
python -m unittest discover -v ./ext/dapr-ext-fastapi/tests
```

- `test_app.py` — uses FastAPI `TestClient` for HTTP-level testing: subscription registration, custom routes, metadata, dead letter topics, router tags
- `test_dapractor.py` — tests `_wrap_response` utility (string, bytes, error, object), router tag propagation across all 6 actor routes

## Key details

- **Async actors**: `register_actor` is an async method (must be awaited). Actor method/timer/reminder handlers are dispatched through `ActorRuntime` which uses `asyncio.run()`.
- **Router tags**: Both classes support `router_tags` parameter to customize OpenAPI/Swagger documentation grouping.
- **No gRPC**: This extension is HTTP-only. It works with Dapr's HTTP callback protocol, not gRPC.
