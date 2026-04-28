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
├── conftest.py              # DaprTestEnvironment + fixtures (dapr_env, apps_dir, resources_dir, crypto_keys)
├── test_*.py                # Test files (one per building block)
├── apps/                    # Helper apps started alongside sidecars
│   ├── invoke_receiver.py   # gRPC method handler for invoke tests
│   └── pubsub_subscriber.py # Subscriber that persists messages to state store
├── resources/               # Dapr component YAMLs loaded by all sidecars
│   ├── statestore.yaml      # state.redis (also configured as actor state store)
│   ├── pubsub.yaml          # pubsub.redis
│   ├── lockstore.yaml       # lock.redis
│   ├── configurationstore.yaml # configuration.redis
│   ├── localsecretstore.yaml   # secretstores.local.file
│   ├── localbinding.yaml    # bindings.localstorage (rootPath=./.binding-data)
│   ├── cryptostore.yaml     # crypto.dapr.localstorage (path=./keys)
│   └── conversation.yaml    # conversation.echo
├── keys/                    # RSA + symmetric keys for cryptostore (generated at test time, gitignored)
├── secrets.json             # Secrets file for localsecretstore component
└── .binding-data/           # Created on demand for localbinding rootPath (gitignored)
```

## Fixtures

Sidecar and client fixtures are **module-scoped** — one sidecar per test file. Helper fixtures may use a different scope; see the table below.

| Fixture | Scope | Type | Description |
|---------|-------|------|-------------|
| `dapr_env` | module | `DaprTestEnvironment` | Manages sidecar lifecycle; call `start_sidecar()` to get a client |
| `apps_dir` | module | `Path` | Path to `tests/integration/apps/` |
| `resources_dir` | module | `Path` | Path to `tests/integration/resources/` |
| `crypto_keys` | session | `Path` | Generates ephemeral RSA + AES keys under `tests/integration/keys/` for the cryptostore component (see `tests/crypto_utils.py`) |
| `flush_redis` | session | `None` | Side-effect fixture that clears the `dapr_redis` container once per session |
| `redis_set_config` | session | `Callable` | Returns `_set(key, value, version=1)` that seeds a Dapr configuration value into Redis (`value||version`) |

`flush_redis` and `redis_set_config` are session-scoped (defined in `tests/conftest.py`) so module-scoped fixtures can depend on them.

Polling helpers are **plain functions**, not fixtures — import them directly:

```python
from tests.wait_utils import wait_until, wait_until_async
```

Both have signature `(condition, timeout=10.0, interval=0.1)` and raise `TimeoutError` if the deadline elapses. `wait_until_async` awaits an awaitable condition.

Each test file defines its own module-scoped fixture (`client` or `sidecar`) that calls `dapr_env.start_sidecar(...)`.

## Building blocks covered

| Test file | Building block | SDK methods tested |
|-----------|---------------|-------------------|
| `test_state_store.py` | State management | `save_state`, `get_state`, `save_bulk_state`, `get_bulk_state`, `execute_state_transaction`, `delete_state` |
| `test_invoke.py` | Service invocation | `invoke_method` |
| `test_pubsub.py` | Pub/sub | `publish_event`, `publish_events`, `get_state` (to verify delivery) |
| `test_secret_store.py` | Secrets | `get_secret`, `get_bulk_secret` |
| `test_metadata.py` | Metadata | `get_metadata`, `set_metadata` |
| `test_distributed_lock.py` | Distributed lock | `try_lock`, `unlock`, context manager |
| `test_configuration.py` | Configuration | `get_configuration`, `subscribe_configuration`, `unsubscribe_configuration` |
| `test_jobs.py` | Jobs scheduler | `schedule_job_alpha1`, `get_job_alpha1`, `delete_job_alpha1` |
| `test_invoke_binding.py` | Output bindings | `invoke_binding` (create/get/delete against `bindings.localstorage`) |
| `test_crypto.py` | Cryptography | `encrypt`, `decrypt` (RSA + AES round-trips against `crypto.dapr.localstorage`) |
| `test_conversation.py` | Conversation | `converse_alpha1`, `converse_alpha2` against `conversation.echo` |
| `test_workflow.py` | Workflow (`dapr-ext-workflow`) | `WorkflowRuntime`, `DaprWorkflowClient.schedule_new_workflow`, `wait_for_workflow_start`, `wait_for_workflow_completion`, `raise_workflow_event`, `pause_workflow`, `resume_workflow`, `terminate_workflow`, `purge_workflow`, `get_workflow_state` |

### Async client coverage

Async counterparts exercise `dapr.aio.clients.DaprClient` (the gRPC async client). Each file mirrors its sync sibling with smoke tests — the sync suite validates SDK logic end-to-end, the async suite verifies the `aio` transport.

| File | Covers |
|------|--------|
| `test_state_store_async.py` | `save_state`, `get_state`, `delete_state`, `execute_state_transaction` |
| `test_invoke_async.py` | `invoke_method` |
| `test_invoke_binding_async.py` | `invoke_binding` (create/get) |
| `test_pubsub_async.py` | `publish_event`, `publish_events` |
| `test_secret_store_async.py` | `get_secret`, `get_bulk_secret` |
| `test_configuration_async.py` | `get_configuration` |
| `test_distributed_lock_async.py` | `try_lock`, `unlock` |
| `test_metadata_async.py` | `get_metadata`, `set_metadata` |
| `test_jobs_async.py` | `schedule_job_alpha1`, `get_job_alpha1`, `delete_job_alpha1` |
| `test_crypto_async.py` | `encrypt`, `decrypt` |
| `test_conversation_async.py` | `converse_alpha1`, `converse_alpha2` |

Async tests use `pytest-asyncio` in auto mode (configured in `pyproject.toml`). Any `async def test_*` is run as a coroutine — no decorator required. The sidecar fixture stays sync (it just starts `dapr run`); each test creates a short-lived `async with AsyncDaprClient(address='127.0.0.1:50001') as d:` block.

## Port allocation

All sidecars default to gRPC port 50001 and HTTP port 3500. Since fixtures are module-scoped and tests run sequentially, only one sidecar is active at a time. If parallel execution is needed in the future, sidecars will need dynamic port allocation.

## Helper apps

Some building blocks (invoke, pubsub) require an app process running alongside the sidecar:

- **`invoke_receiver.py`** — A `dapr.ext.grpc.App` that handles `my-method` and returns `INVOKE_RECEIVED`.
- **`pubsub_subscriber.py`** — Subscribes to `TOPIC_A` and persists received messages to the state store. This lets tests verify message delivery by reading state rather than parsing stdout.

## Adding a new test

1. Create `test_<building_block>.py`
2. Add a module-scoped `client` fixture that calls `dapr_env.start_sidecar(app_id='test-<name>')`
3. If the building block needs a new Dapr component, add a YAML to `resources/`
4. If the building block needs a running app, add it to `apps/` and pass `app_cmd` / `app_port` to `start_sidecar()`
5. Use unique keys/resource IDs per test to avoid interference (the sidecar is shared within a module)
6. Assert on SDK return types and gRPC status codes, not on string output

## Gotchas

- **Requires `dapr init`** — the tests assume a local Dapr runtime with Redis (`dapr_redis` container on `localhost:6379`), which `dapr init` sets up automatically.
- **Configuration tests seed Redis directly** via `docker exec dapr_redis redis-cli`.
- **Alpha-API tests suppress `UserWarning`** via
- `pytestmark = pytest.mark.filterwarnings('ignore::UserWarning')`. The SDK's alpha APIs (lock, crypto, jobs) emit a `UserWarning` per call. In production this is dedup'd to one emission per call site by Python's default warning filter (`__warningregistry__`), but pytest resets that registry between tests via its per-test `catch_warnings` context, so the warning re-fires in every test. The suppression is a pytest workaround, not a sign of a bug in the SDK.
- **`localsecretstore.yaml` uses a relative path** (`secrets.json`) resolved against `cwd=INTEGRATION_DIR`. Same pattern applies to `localbinding.yaml` (`./.binding-data`) and `cryptostore.yaml` (`./keys`).
- **`bindings.localstorage` refuses to initialize if `rootPath` does not exist** — `conftest.py` creates `.binding-data/` at import time so every sidecar can load the component.
- **`statestore.yaml` has `actorStateStore: "true"`** because workflow uses the actor runtime. The flag is additive — regular state tests are unaffected.
- **Workflow tests run the `WorkflowRuntime` in-process** and connect to the sidecar's gRPC port (default 50001). No external app is needed.
- **Dapr may normalize response fields** — e.g., `content_type` may lose charset parameters when proxied through gRPC. Assert on the media type prefix, not the full string.
- **Error shapes vary** — `invoke_binding` surfaces sidecar errors as raw `grpc.RpcError`, while other APIs (jobs, state) wrap them in `DaprGrpcError`. Match what the method actually raises.
