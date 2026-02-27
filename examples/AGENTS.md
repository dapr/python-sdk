# AGENTS.md — Dapr Python SDK Examples

The `examples/` directory serves as both **user-facing documentation** and the project's **integration test suite**. Each example is a self-contained application validated automatically in CI using [mechanical-markdown](https://pypi.org/project/mechanical-markdown/), which executes bash code blocks embedded in README files and asserts expected output.

## How validation works

1. `examples/validate.sh` is the entry point — it `cd`s into an example directory and runs `mm.py -l README.md`
2. `mm.py` (mechanical-markdown) parses `<!-- STEP -->` HTML comment blocks in the README
3. Each STEP block wraps a fenced bash code block that gets executed
4. stdout/stderr is captured and checked against `expected_stdout_lines` / `expected_stderr_lines`
5. Validation fails if any expected output line is missing

Run examples locally (requires a running Dapr runtime via `dapr init`):

```bash
# All examples
tox -e examples

# Single example
tox -e example-component -- state_store

# Or directly
cd examples && ./validate.sh state_store
```

In CI (`validate_examples.yaml`), examples run on all supported Python versions (3.10-3.14) on Ubuntu with a full Dapr runtime including Docker, Redis, and (for LLM examples) Ollama.

## Example directory structure

Each example follows this pattern:

```
examples/<example-name>/
├── README.md              # Documentation + mechanical-markdown STEP blocks (REQUIRED)
├── *.py                   # Python application files
├── requirements.txt       # Dependencies (e.g., dapr>=1.17.0rc6)
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

## Mechanical-markdown STEP block format

STEP blocks are HTML comments wrapping fenced bash code in the README:

````markdown
<!-- STEP
name: Run the example
expected_stdout_lines:
  - '== APP == Got state: value'
  - '== APP == State deleted'
background: false
sleep: 5
timeout_seconds: 30
output_match_mode: substring
match_order: none
-->

```bash
dapr run --app-id myapp --resources-path ./components/ python3 example.py
```

<!-- END_STEP -->
````

### STEP block attributes

| Attribute | Description |
|-----------|-------------|
| `name` | Descriptive name for the step |
| `expected_stdout_lines` | List of strings that must appear in stdout |
| `expected_stderr_lines` | List of strings that must appear in stderr |
| `background` | `true` to run in background (for long-running services) |
| `sleep` | Seconds to wait after starting before moving to the next step |
| `timeout_seconds` | Max seconds before the step is killed |
| `output_match_mode` | `substring` for partial matching (default is exact) |
| `match_order` | `none` if output lines can appear in any order |

### Tips for writing STEP blocks

- Use `background: true` with `sleep:` for services that need to stay running (servers, subscribers)
- Use `timeout_seconds:` to prevent CI hangs on broken examples
- Use `output_match_mode: substring` when output contains timestamps or dynamic content
- Use `match_order: none` when multiple concurrent operations produce unpredictable ordering
- Always include a cleanup step (e.g., `dapr stop --app-id ...`) when using background processes
- Make `expected_stdout_lines` specific enough to validate correctness, but not so brittle they break on cosmetic changes
- Dapr prefixes app output with `== APP ==` — use this in expected lines

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
4. Write a `README.md` with:
   - Introduction explaining what the example demonstrates
   - Pre-requisites section (Dapr CLI, Python 3.10+, any special tools)
   - Install instructions (`pip3 install dapr dapr-ext-grpc` etc.)
   - Running instructions with `<!-- STEP -->` blocks wrapping `dapr run` commands
   - Expected output section
   - Cleanup step to stop background processes
5. Register the example in `tox.ini` under `[testenv:examples]` commands:
   ```
   ./validate.sh your-example-name
   ```
6. Test locally: `cd examples && ./validate.sh your-example-name`

## Common README template

```markdown
# Dapr [Building Block] Example

This example demonstrates how to use the Dapr [building block] API with the Python SDK.

## Pre-requisites

- [Dapr CLI and initialized environment](https://docs.dapr.io/getting-started)
- Python 3.10+

## Install Dapr python-SDK

\`\`\`bash
pip3 install dapr dapr-ext-grpc
\`\`\`

## Run the example

<!-- STEP
name: Run example
expected_stdout_lines:
  - '== APP == Expected output here'
timeout_seconds: 30
-->

\`\`\`bash
dapr run --app-id myapp --resources-path ./components/ python3 example.py
\`\`\`

<!-- END_STEP -->

## Cleanup

<!-- STEP
name: Cleanup
-->

\`\`\`bash
dapr stop --app-id myapp
\`\`\`

<!-- END_STEP -->
```

## Gotchas

- **Output format changes break CI**: If you modify print statements or log output in SDK code, check whether any example's `expected_stdout_lines` depend on that output.
- **Background processes must be cleaned up**: Missing cleanup steps cause CI to hang.
- **Dapr prefixes output**: Application stdout appears as `== APP == <line>` when run via `dapr run`.
- **Redis is available in CI**: The CI environment has Redis running on `localhost:6379` — most component YAMLs use this.
- **Some examples need special setup**: `crypto` generates keys, `configuration` seeds Redis, `conversation` needs LLM config — check individual READMEs.
