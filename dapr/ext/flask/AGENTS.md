# AGENTS.md — dapr.ext.flask

The Flask extension provides two integration classes for building Dapr applications with [Flask](https://flask.palletsprojects.com/): `DaprApp` for pub/sub subscriptions and `DaprActor` for actor hosting. It mirrors the FastAPI extension's functionality but uses Flask's routing and request model.

## Source layout

```
dapr/ext/flask/
├── __init__.py                # Exports: DaprApp, DaprActor
├── app.py                     # DaprApp — pub/sub subscription handler
├── actor.py                   # DaprActor — actor runtime HTTP adapter
└── py.typed

tests/ext/flask/
├── test_app.py                # DaprApp pub/sub tests
└── test_shim_deprecation.py   # Locks the legacy `flask_dapr` shim contract
```

Installed via the `flask` extra on core dapr: `pip install "dapr[flask]"`.

The legacy top-level import path (`from flask_dapr import DaprApp, DaprActor`) is still supported through a thin shim at the repo root that emits a `FutureWarning`. The shim is kept through 1.21 and removed in 1.22, giving users on 1.18 (the last release to ship the standalone distributions) the full N-2 support window to migrate. All new code and docs should use the canonical `from dapr.ext.flask import ...` path.

## Public API

```python
from dapr.ext.flask import DaprApp, DaprActor
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

## Dependencies (declared via the `flask` extra in the root `pyproject.toml`)

- `dapr` (core, same wheel as this extension)
- `Flask >= 1.1.4, < 4.0.0`

## Testing

```bash
# Unittest-style tests (test_app.py)
uv run python -m unittest discover -v ./tests/ext/flask

# The shim deprecation test is pytest-style — run with pytest
uv run pytest tests/ext/flask
```

- `test_app.py` — uses Flask `test_client()` for HTTP-level testing: subscription registration, custom routes, metadata, dead letter topics
- `test_shim_deprecation.py` — asserts that `import flask_dapr` emits `FutureWarning` and re-exports `DaprApp`/`DaprActor` correctly

Note: No tests for `DaprActor` in this extension (unlike FastAPI which tests `_wrap_response`).

## Key details

- **Synchronous + asyncio bridge**: Flask is sync, but `ActorRuntime` is async. The extension uses `asyncio.run()` for each actor operation.
- **Canonical import path**: Use `from dapr.ext.flask import DaprApp, DaprActor`. The legacy `flask_dapr` top-level path still works but emits `FutureWarning` and will be removed in 1.22.
- **Similar to FastAPI extension**: The two extensions have nearly identical functionality. When modifying one, check if the same change is needed in the other.
- **Reentrancy ID**: Actor method invocation extracts `Dapr-Reentrancy-Id` header, same as FastAPI extension.