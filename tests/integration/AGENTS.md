# AGENTS.md — Programmatic Integration Tests

This directory contains **programmatic SDK tests** that call `DaprClient` methods directly and assert on return values, gRPC status codes, and SDK types. Unlike the output-based tests in `tests/examples/` (which run example scripts and check stdout), these tests don't depend on print statement formatting.

## How it works

1. `DaprTestEnvironment` (defined in `conftest.py`) manages Dapr sidecar processes
2. `start_sidecar()` launches `dapr run` with explicit ports, waits for the health check, and returns a connected `DaprClient`
3. Tests call SDK methods on that client and assert on the response objects
4. Sidecar stdout is written to temp files (not pipes) to avoid buffer deadlocks
5. Cleanup terminates sidecars, closes clients, and removes log files

Run locally (requires a running Dapr runtime via `dapr init`):

```bash
# All integration tests
tox -e integration

# Single test file
tox -e integration -- test_state_store.py

# Single test
tox -e integration -- test_state_store.py -k test_save_and_get
```

## Directory structure

```
tests/integration/
├── conftest.py              # DaprTestEnvironment + fixtures (dapr_env, apps_dir, components_dir)
├── test_*.py                # Test files (one per building block)
├── apps/                    # Helper apps started alongside sidecars
│   ├── invoke_receiver.py   # gRPC method handler for invoke tests
│   └── pubsub_subscriber.py # Subscriber that persists messages to state store
├── components/              # Dapr component YAMLs loaded by all sidecars
│   ├── statestore.yaml      # state.redis
│   ├── pubsub.yaml          # pubsub.redis
│   ├── lockstore.yaml       # lock.redis
│   ├── configurationstore.yaml # configuration.redis
│   └── localsecretstore.yaml   # secretstores.local.file
└── secrets.json             # Secrets file for localsecretstore component
```

## Fixtures

Sidecar and client fixtures are **module-scoped** — one sidecar per test file. Helper fixtures may use a different scope; see the table below.

| Fixture | Scope | Type | Description |
|---------|-------|------|-------------|
| `dapr_env` | module | `DaprTestEnvironment` | Manages sidecar lifecycle; call `start_sidecar()` to get a client |
| `apps_dir` | module | `Path` | Path to `tests/integration/apps/` |
| `components_dir` | module | `Path` | Path to `tests/integration/components/` |
| `wait_until` | function | `Callable` | Polling helper `(predicate, timeout=10, interval=0.1)` for eventual-consistency assertions |

Each test file defines its own module-scoped `client` fixture that calls `dapr_env.start_sidecar(...)`.

## Building blocks covered

| Test file | Building block | SDK methods tested |
|-----------|---------------|-------------------|
| `test_state_store.py` | State management | `save_state`, `get_state`, `save_bulk_state`, `get_bulk_state`, `execute_state_transaction`, `delete_state` |
| `test_invoke.py` | Service invocation | `invoke_method` |
| `test_pubsub.py` | Pub/sub | `publish_event`, `get_state` (to verify delivery) |
| `test_secret_store.py` | Secrets | `get_secret`, `get_bulk_secret` |
| `test_metadata.py` | Metadata | `get_metadata`, `set_metadata` |
| `test_distributed_lock.py` | Distributed lock | `try_lock`, `unlock`, context manager |
| `test_configuration.py` | Configuration | `get_configuration`, `subscribe_configuration`, `unsubscribe_configuration` |

## Port allocation

All sidecars default to gRPC port 50001 and HTTP port 3500. Since fixtures are module-scoped and tests run sequentially, only one sidecar is active at a time. If parallel execution is needed in the future, sidecars will need dynamic port allocation.

## Helper apps

Some building blocks (invoke, pubsub) require an app process running alongside the sidecar:

- **`invoke_receiver.py`** — A `dapr.ext.grpc.App` that handles `my-method` and returns `INVOKE_RECEIVED`.
- **`pubsub_subscriber.py`** — Subscribes to `TOPIC_A` and persists received messages to the state store. This lets tests verify message delivery by reading state rather than parsing stdout.

## Adding a new test

1. Create `test_<building_block>.py`
2. Add a module-scoped `client` fixture that calls `dapr_env.start_sidecar(app_id='test-<name>')`
3. If the building block needs a new Dapr component, add a YAML to `components/`
4. If the building block needs a running app, add it to `apps/` and pass `app_cmd` / `app_port` to `start_sidecar()`
5. Use unique keys/resource IDs per test to avoid interference (the sidecar is shared within a module)
6. Assert on SDK return types and gRPC status codes, not on string output

## Gotchas

- **Requires `dapr init`** — the tests assume a local Dapr runtime with Redis (`dapr_redis` container on `localhost:6379`), which `dapr init` sets up automatically.
- **Configuration tests seed Redis directly** via `docker exec dapr_redis redis-cli`.
- **Lock and configuration APIs are alpha** and emit `UserWarning` on every call. Tests suppress these with `pytestmark = pytest.mark.filterwarnings('ignore::UserWarning')`.
- **`localsecretstore.yaml` uses a relative path** (`secrets.json`) resolved against `cwd=INTEGRATION_DIR`.
- **Dapr may normalize response fields** — e.g., `content_type` may lose charset parameters when proxied through gRPC. Assert on the media type prefix, not the full string.
