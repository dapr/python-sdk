## Workflow tests: unit, integration, and custom ports

This directory contains unit tests (no sidecar required) and integration tests (require a running sidecar/runtime).

### Prereqs

- Python 3.11+ (tox will create an isolated venv)
- Dapr sidecar for integration tests (HTTP and gRPC ports)
- Optional: Durable Task gRPC endpoint for DT e2e tests

### Run all tests via tox (recommended)

```bash
tox -e py311
```

This runs:
- Core SDK tests (unittest)
- Workflow extension unit tests (pytest)
- Workflow extension integration tests (pytest) if your sidecar/runtime is reachable

### Run only workflow unit tests

Unit tests live at `ext/dapr-ext-workflow/tests` excluding the `integration/` subfolder.

With tox:
```bash
tox -e py311 -- pytest -q ext/dapr-ext-workflow/tests -k "not integration"
```

Directly (outside tox):
```bash
pytest -q ext/dapr-ext-workflow/tests -k "not integration"
```

### Run workflow integration tests

Integration tests live under `ext/dapr-ext-workflow/tests/integration/` and require a running sidecar/runtime.

With tox:
```bash
tox -e py311 -- pytest -q ext/dapr-ext-workflow/tests/integration
```

Directly (outside tox):
```bash
pytest -q ext/dapr-ext-workflow/tests/integration
```

If tests cannot reach your sidecar/runtime, they will skip or fail fast depending on the specific test.

### Configure custom sidecar ports/endpoints

The SDK reads connection settings from env vars (see `dapr.conf.global_settings`). Use these to point tests at custom ports:

- Dapr gRPC:
  - `DAPR_GRPC_ENDPOINT` (preferred): endpoint string, e.g. `dns:127.0.0.1:50051`
  - or `DAPR_RUNTIME_HOST` and `DAPR_GRPC_PORT`, e.g. `DAPR_RUNTIME_HOST=127.0.0.1`, `DAPR_GRPC_PORT=50051`

- Dapr HTTP (only for HTTP-based tests):
  - `DAPR_HTTP_ENDPOINT`: e.g. `http://127.0.0.1:3600`
  - or `DAPR_RUNTIME_HOST` and `DAPR_HTTP_PORT`, e.g. `DAPR_HTTP_PORT=3600`

Examples:
```bash
# Use custom gRPC 50051 and HTTP 3600
export DAPR_GRPC_ENDPOINT=dns:127.0.0.1:50051
export DAPR_HTTP_ENDPOINT=http://127.0.0.1:3600

# Alternatively, using host/port pairs
export DAPR_RUNTIME_HOST=127.0.0.1
export DAPR_GRPC_PORT=50051
export DAPR_HTTP_PORT=3600

tox -e py311 -- pytest -q ext/dapr-ext-workflow/tests/integration
```

Note: For gRPC, avoid `http://` or `https://` schemes. Use `dns:host:port` or just set host/port separately.

### Durable Task e2e tests (optional)

Some tests (e.g., `integration/test_async_e2e_dt.py`) talk directly to a Durable Task gRPC endpoint. They use:

- `DURABLETASK_GRPC_ENDPOINT` (default `localhost:56178`)

If your DT runtime listens elsewhere:
```bash
export DURABLETASK_GRPC_ENDPOINT=127.0.0.1:56179
tox -e py311 -- pytest -q ext/dapr-ext-workflow/tests/integration/test_async_e2e_dt.py
```




