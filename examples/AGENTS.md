# AGENTS.md — Dapr Python SDK Examples

The `examples/` directory serves as both **user-facing documentation** and the project's **integration test suite**. Each example is a self-contained application validated by pytest-based integration tests in `tests/integration/`.

## How validation works

1. Each example has a corresponding test file in `tests/integration/` (e.g., `test_state_store.py`)
2. Tests use a `DaprRunner` helper (defined in `conftest.py`) that wraps `dapr run` commands
3. `DaprRunner.run()` executes a command and captures stdout; `DaprRunner.start()`/`stop()` manage background services
4. Tests assert that expected output lines appear in the captured output

Run examples locally (requires a running Dapr runtime via `dapr init`):

```bash
# All examples
tox -e examples

# Single example
tox -e examples -- test_state_store.py
```

In CI (`validate_examples.yaml`), examples run on all supported Python versions (3.10-3.14) on Ubuntu with a full Dapr runtime including Docker, Redis, and (for LLM examples) Ollama.

## Example directory structure

Each example follows this pattern:

```
examples/<example-name>/
├── README.md              # Documentation (REQUIRED)
├── *.py                   # Python application files
├── requirements.txt       # Dependencies (optional — many examples rely on the installed SDK)
├── components/            # Dapr component YAML configs (if needed)
│   ├── statestore.yaml
│   └── pubsub.yaml
├── config.yaml            # Dapr configuration (optional, e.g., for tracing/features)
└── proto/                 # Protobuf definitions (for gRPC examples)
```

Common Python file naming conventions:
- Server/receiver side: `*-receiver.py`, `subscriber.py`, `*_service.py`
- Client/caller side: `*-caller.py`, `publisher.py`, `*_client.py`
- Standalone: `state_store.py`, `crypto.py`, etc.

## Dapr component YAML format

Components in `components/` directories follow the standard Dapr resource format:

```yaml
apiVersion: dapr.io/v1alpha1
kind: Component
metadata:
  name: statestore
spec:
  type: state.redis
  version: v1
  metadata:
  - name: redisHost
    value: localhost:6379
  - name: redisPassword
    value: ""
```

Common component types used in examples: `state.redis`, `pubsub.redis`, `lock.redis`, `configuration.redis`, `crypto.dapr.localstorage`, `bindings.*`.

## All examples by building block

### State management
| Example | Pattern | SDK packages | Has components |
|---------|---------|-------------|----------------|
| `state_store` | Standalone client | `dapr`, `dapr-ext-grpc` | Yes |
| `state_store_query` | Standalone client | `dapr`, `dapr-ext-grpc` | Yes |

### Service invocation
| Example | Pattern | SDK packages | Has components |
|---------|---------|-------------|----------------|
| `invoke-simple` | Client-server (receiver/caller) | `dapr`, `dapr-ext-grpc` | No |
| `invoke-custom-data` | Client-server (protobuf) | `dapr`, `dapr-ext-grpc` | No |
| `invoke-http` | Client-server (Flask) | `dapr`, Flask | No |
| `invoke-binding` | Client with bindings | `dapr`, `dapr-ext-grpc` | Yes |
| `grpc_proxying` | Client-server (gRPC proxy) | `dapr`, `dapr-ext-grpc` | No (has config.yaml) |

### Pub/sub
| Example | Pattern | SDK packages | Has components |
|---------|---------|-------------|----------------|
| `pubsub-simple` | Client-server (publisher/subscriber) | `dapr`, `dapr-ext-grpc` | No |
| `pubsub-streaming` | Streaming pub/sub | `dapr` (base only) | No |
| `pubsub-streaming-async` | Async streaming pub/sub | `dapr` (base only) | No |

### Virtual actors
| Example | Pattern | SDK packages | Has components |
|---------|---------|-------------|----------------|
| `demo_actor` | Client-server (FastAPI/Flask + client) | `dapr`, `dapr-ext-fastapi` | No |

### Workflow
| Example | Pattern | SDK packages | Has components |
|---------|---------|-------------|----------------|
| `workflow` | Multiple standalone scripts | `dapr-ext-workflow`, `dapr` | No |
| `demo_workflow` | Legacy (deprecated DaprClient methods) | `dapr-ext-workflow` | Yes |

The `workflow` example includes: `simple.py`, `task_chaining.py`, `fan_out_fan_in.py`, `human_approval.py`, `monitor.py`, `child_workflow.py`, `cross-app1/2/3.py`, `versioning.py`, `simple_aio_client.py`.

### Secrets, configuration, locks
| Example | Pattern | SDK packages | Has components |
|---------|---------|-------------|----------------|
| `secret_store` | Standalone client | `dapr`, `dapr-ext-grpc` | Yes |
| `configuration` | Standalone client with subscription | `dapr`, `dapr-ext-grpc` | Yes |
| `distributed_lock` | Standalone client | `dapr`, `dapr-ext-grpc` | Yes |

### Cryptography
| Example | Pattern | SDK packages | Has components |
|---------|---------|-------------|----------------|
| `crypto` | Standalone (sync + async) | `dapr`, `dapr-ext-grpc` | Yes |

### Jobs, tracing, metadata, errors
| Example | Pattern | SDK packages | Has components |
|---------|---------|-------------|----------------|
| `jobs` | Standalone + gRPC event handler | `dapr`, `dapr-ext-grpc` | No |
| `w3c-tracing` | Client-server with OpenTelemetry | `dapr`, `dapr-ext-grpc`, OpenTelemetry | No |
| `metadata` | Standalone client | `dapr`, `dapr-ext-grpc` | Yes |
| `error_handling` | Standalone client | `dapr`, `dapr-ext-grpc` | Yes |

### AI/LLM integrations
| Example | Pattern | SDK packages | Has components |
|---------|---------|-------------|----------------|
| `conversation` | Standalone client | `dapr` (base, uses sidecar) | No (uses config/) |
| `langgraph-checkpointer` | Standalone gRPC server | `dapr-ext-langgraph`, LangGraph, LangChain | Yes |

## Adding a new example

1. Create a directory under `examples/` with a descriptive kebab-case name
2. Add Python source files and a `requirements.txt` referencing the needed SDK packages
3. Add Dapr component YAMLs in a `components/` subdirectory if the example uses state, pubsub, etc.
4. Write a `README.md` with introduction, pre-requisites, install instructions, and running instructions
5. Add a corresponding test in `tests/integration/test_<example_name>.py`:
   - Use the `@pytest.mark.example_dir('<example-name>')` marker to set the working directory
   - Use `dapr.run()` for scripts that exit on their own, `dapr.start()`/`dapr.stop()` for long-running services
   - Assert expected output lines appear in the captured output
6. Test locally: `tox -e integration -- test_<example_name>.py`

## Gotchas

- **Output format changes break tests**: If you modify print statements or log output in SDK code, check whether any integration test's expected lines depend on that output.
- **Background processes must be cleaned up**: The `DaprRunner` fixture handles cleanup on teardown, but tests should still call `dapr.stop()` to capture output.
- **Dapr prefixes output**: Application stdout appears as `== APP == <line>` when run via `dapr run`.
- **Redis is available in CI**: The CI environment has Redis running on `localhost:6379` — most component YAMLs use this.
- **Some examples need special setup**: `crypto` generates keys, `configuration` seeds Redis, `conversation` needs LLM config — check individual READMEs.
- **Infinite-loop example scripts**: Some example scripts (e.g., `invoke-caller.py`) have `while True` loops for demo purposes. Integration tests must either bypass these with HTTP API calls or use `dapr.run(until=...)` for early termination.