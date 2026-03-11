# AGENTS.md — flask_dapr

The Flask extension provides two integration classes for building Dapr applications with [Flask](https://flask.palletsprojects.com/): `DaprApp` for pub/sub subscriptions and `DaprActor` for actor hosting. It mirrors the FastAPI extension's functionality but uses Flask's routing and request model.

## Source layout

```
ext/flask_dapr/
├── setup.cfg                      # Deps: dapr, Flask
├── setup.py
├── tests/
│   └── test_app.py                # DaprApp pub/sub tests
└── flask_dapr/
    ├── __init__.py                # Exports: DaprApp, DaprActor
    ├── app.py                     # DaprApp — pub/sub subscription handler
    ├── actor.py                   # DaprActor — actor runtime HTTP adapter
    └── version.py
```

Note: Unlike other extensions, this package uses `flask_dapr` as its top-level namespace (not `dapr.ext.*`).

## Public API

```python
from flask_dapr import DaprApp, DaprActor
```

### DaprApp (`app.py`)

Wraps a Flask instance to add Dapr pub/sub event handling.

```python
app = Flask('myapp')
dapr_app = DaprApp(app)

@dapr_app.subscribe(pubsub='pubsub', topic='orders', route='/handle-order',
                     metadata={}, dead_letter_topic=None)
def handle_order():
    event_data = request.json
    return 'ok'
```

- Auto-registers `GET /dapr/subscribe` endpoint
- Each `@subscribe` registers a POST route via `add_url_rule()`
- Default route: `/events/{pubsub}/{topic}`
- Handlers use Flask's `request` context (not function arguments)

### DaprActor (`actor.py`)

Integrates Dapr's actor runtime with Flask.

```python
app = Flask('actor_service')
dapr_actor = DaprActor(app)
dapr_actor.register_actor(MyActorClass)
```

Auto-registers six endpoints (same as FastAPI extension):
- `GET /healthz`, `GET /dapr/config`
- `DELETE /actors/{type}/{id}` — deactivation
- `PUT /actors/{type}/{id}/method/{method}` — method invocation
- `PUT /actors/{type}/{id}/method/timer/{timer}`, `PUT /actors/{type}/{id}/method/remind/{reminder}`

**Async bridging**: Uses `asyncio.run()` to bridge Flask's synchronous request handling with the async `ActorRuntime`. Each handler call spawns a new event loop.

**Response wrapping** (`wrap_response`): Same pattern as FastAPI extension — string → JSON, bytes → raw, dict → JSON. Error responses include `errorCode` field.

## Dependencies

- `dapr >= 1.17.0.dev`
- `Flask >= 1.1`

## Testing

```bash
python -m unittest discover -v ./ext/flask_dapr/tests
```

- `test_app.py` — uses Flask `test_client()` for HTTP-level testing: subscription registration, custom routes, metadata, dead letter topics

Note: No tests for `DaprActor` in this extension (unlike FastAPI which tests `_wrap_response`).

## Key details

- **Synchronous + asyncio bridge**: Flask is sync, but `ActorRuntime` is async. The extension uses `asyncio.run()` for each actor operation.
- **Different namespace**: This is `flask_dapr`, not `dapr.ext.flask`. Import as `from flask_dapr import DaprApp, DaprActor`.
- **Similar to FastAPI extension**: The two extensions have nearly identical functionality. When modifying one, check if the same change is needed in the other.
- **Reentrancy ID**: Actor method invocation extracts `Dapr-Reentrancy-Id` header, same as FastAPI extension.
