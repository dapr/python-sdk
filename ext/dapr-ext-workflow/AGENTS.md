# AGENTS.md — dapr-ext-workflow

The workflow extension is a **major area of active development**. It provides durable workflow orchestration for Python, built on a vendored durabletask engine (in `_durabletask/`).

## Source layout

```
ext/dapr-ext-workflow/
├── pyproject.toml                         # Deps: dapr (durabletask is vendored)
├── setup.py
├── tests/
│   ├── test_dapr_workflow_context.py      # Context method proxying
│   ├── test_workflow_activity_context.py  # Activity context properties
│   ├── test_workflow_client.py            # Sync client (mock gRPC)
│   ├── test_workflow_client_aio.py        # Async client (IsolatedAsyncioTestCase)
│   ├── test_workflow_runtime.py           # Registration, decorators, worker readiness
│   └── test_workflow_util.py              # Address resolution
└── dapr/ext/workflow/
    ├── __init__.py                        # Public API exports
    ├── workflow_runtime.py                # WorkflowRuntime — registration & lifecycle
    ├── dapr_workflow_client.py            # DaprWorkflowClient (sync)
    ├── aio/dapr_workflow_client.py        # DaprWorkflowClient (async)
    ├── dapr_workflow_context.py           # DaprWorkflowContext + when_all/when_any
    ├── workflow_context.py                # WorkflowContext ABC
    ├── workflow_activity_context.py       # WorkflowActivityContext wrapper
    ├── workflow_state.py                  # WorkflowState, WorkflowStatus enum
    ├── retry_policy.py                    # RetryPolicy wrapper
    ├── util.py                            # gRPC address resolution
    ├── logger/options.py                  # LoggerOptions
    └── logger/logger.py                   # Logger wrapper
```

## Architecture

```
┌──────────────────────────────────────────────────┐
│  User code: @wfr.workflow / @wfr.activity        │
└──────────────────┬───────────────────────────────┘
                   │
┌──────────────────▼───────────────────────────────┐
│  WorkflowRuntime                                  │
│  - Decorator-based registration                   │
│  - Wraps user functions with context wrappers     │
│  - Manages TaskHubGrpcWorker lifecycle            │
└──────────────────┬───────────────────────────────┘
                   │
┌──────────────────▼───────────────────────────────┐
│  DaprWorkflowContext / WorkflowActivityContext    │
│  - Proxy wrappers around durabletask contexts     │
│  - Adds Dapr-specific features (app_id, logging) │
└──────────────────┬───────────────────────────────┘
                   │
┌──────────────────▼───────────────────────────────┐
│  DaprWorkflowClient (sync) / (async)             │
│  - Schedule, query, pause, resume, terminate      │
│  - Wraps TaskHubGrpcClient                        │
└──────────────────┬───────────────────────────────┘
                   │
┌──────────────────▼───────────────────────────────┐
│  _durabletask (vendored internal package)          │
│  - TaskHubGrpcWorker: receives work items         │
│  - TaskHubGrpcClient: manages orchestrations      │
│  - OrchestrationContext / ActivityContext          │
│  - History replay engine (deterministic execution)│
└──────────────────┬───────────────────────────────┘
                   │
                   ▼
            Dapr sidecar (gRPC)
```

## Public API

All public symbols are exported from `dapr.ext.workflow`:

```python
from dapr.ext.workflow import (
    WorkflowRuntime,          # Registration & lifecycle (start/shutdown)
    DaprWorkflowClient,       # Sync client for scheduling/managing workflows
    DaprWorkflowContext,      # Passed to workflow functions as first arg
    WorkflowActivityContext,  # Passed to activity functions as first arg
    WorkflowState,            # Snapshot of a workflow instance's state
    WorkflowStatus,           # Enum: UNKNOWN, RUNNING, COMPLETED, FAILED, TERMINATED, PENDING, SUSPENDED, STALLED
    when_all,                 # Parallel combinator — wait for all tasks
    when_any,                 # Race combinator — wait for first task
    alternate_name,           # Decorator to set a custom registration name
    RetryPolicy,              # Retry config for activities/child workflows
)

# Async client:
from dapr.ext.workflow.aio import DaprWorkflowClient  # async variant
```

## Key classes

### WorkflowRuntime (`workflow_runtime.py`)

The entry point for registration and lifecycle:

- `register_workflow(fn, *, name=None)` / `@workflow(name=None)` decorator
- `register_activity(fn, *, name=None)` / `@activity(name=None)` decorator
- `register_versioned_workflow(fn, *, name, version_name, is_latest)` / `@versioned_workflow(...)` decorator
- `start()` — starts the gRPC worker, waits for stream readiness
- `shutdown()` — stops the worker
- `wait_for_worker_ready(timeout=30.0)` — polls worker readiness

Internally wraps user functions: workflow functions get a `DaprWorkflowContext`, activity functions get a `WorkflowActivityContext`. Tracks registration state via `_workflow_registered` / `_activity_registered` attributes on functions to prevent double registration.

#### Sync and async activities

Activities can be either `def my_activity(ctx, inp)` or `async def my_activity(ctx, inp)`. At registration, `_make_activity_wrapper` calls `_is_async_callable(fn)` to detect async-ness. That helper unwraps `functools.partial`, `@functools.wraps` chains, and callable-class `__call__` so common decorator patterns route correctly. The wrapper is built `async def` or `def` to match, then stored in the registry.

At dispatch time (the gRPC stream loop in `_durabletask/worker.py`), `inspect.iscoroutinefunction(activity_fn)` on the wrapper selects between two handlers.

- **Async activities** go through `_execute_activity_async`, then `_ActivityExecutor.execute_async`, which awaits `fn(...)` directly on the event loop. No thread pool involvement. The gRPC response is delivered via `loop.run_in_executor(None, stub.CompleteActivityTask, ...)` (asyncio's default executor).
- **Sync activities** go through `_execute_activity`, dispatched to the thread pool by `_AsyncWorkerManager._run_func`. The activity runs on a worker thread, and the response is delivered from the same thread. The thread pool size is controlled by `maximum_thread_pool_workers`.

Workflow (orchestrator) functions must remain generators (`def` with `yield`). They cannot be `async def` because durabletask's deterministic replay depends on synchronous generator semantics. Only activities support async.

**Decorator ordering gotcha.** Stacking `@wfr.activity` over `@alternate_name(...)` over `async def` works because `@alternate_name` now emits an `async def innerfn` when the wrapped function is async. A user-written decorator that wraps an async function in a sync `def` (without `@functools.wraps` exposing `__wrapped__`) defeats `_is_async_callable`, routes the activity to the sync path, and produces an un-awaited coroutine. Such decorators should use `@functools.wraps(fn)` so the unwrap walks through them.

**`maximum_thread_pool_workers` gotcha.** This knob sizes the sync-activity thread pool only. Async-activity response delivery uses the default executor of the worker's own event loop (a separate object lazily sized to `min(32, cpu_count + 4)`), which is not capped by this knob. The default executor is per-loop, and `TaskHubGrpcWorker.start()` creates `loop_worker` via `asyncio.new_event_loop()` on a background thread, so a `set_default_executor(...)` call in application code targets a different loop and has no effect. There is no SDK hook today to configure `loop_worker`'s executor. To bound response-delivery concurrency, lower `maximum_concurrent_activity_work_items` so fewer async activities finish at once.

**Concurrency sizing and load characterization.** See `docs/concurrency.md` for sizing recommendations (`maximum_concurrent_activity_work_items`, `maximum_thread_pool_workers`), an async-vs-sync decision tree, and the default-executor caveat with a worked example. The `benchmarks/` directory ships `bench_async_activities.py`; re-run it locally before claiming a perf regression. The generated `RESULTS.md` is gitignored because numbers are machine-specific; see `docs/concurrency.md` for the regen command.


### DaprWorkflowClient (`dapr_workflow_client.py`)

Client for workflow lifecycle management:

- `schedule_new_workflow(workflow, *, input, instance_id, start_at, reuse_id_policy)` → returns `instance_id`
- `get_workflow_state(instance_id, *, fetch_payloads=True)` → `Optional[WorkflowState]`
- `wait_for_workflow_start(instance_id, *, fetch_payloads, timeout_in_seconds)`
- `wait_for_workflow_completion(instance_id, *, fetch_payloads, timeout_in_seconds)`
- `raise_workflow_event(instance_id, event_name, *, data)`
- `terminate_workflow(instance_id, *, output, recursive)`
- `pause_workflow(instance_id)` / `resume_workflow(instance_id)`
- `purge_workflow(instance_id, *, recursive)`
- `close()` — close gRPC connection

Converts gRPC "no such instance exists" errors to `None` returns. The async variant in `aio/` has the same API with `async` methods.

### DaprWorkflowContext (`dapr_workflow_context.py`)

Passed to workflow functions as the first argument:

- `instance_id`, `current_utc_datetime`, `is_replaying` — properties
- `call_activity(activity, *, input, retry_policy, app_id)` → `Task`
- `call_child_workflow(workflow, *, input, instance_id, retry_policy, app_id)` → `Task`
- `create_timer(fire_at)` → `Task` (accepts `datetime` or `timedelta`)
- `wait_for_external_event(name)` → `Task`
- `set_custom_status(status)` / `continue_as_new(new_input, *, save_events)`

Module-level functions:
- `when_all(tasks)` → `WhenAllTask` — wait for all tasks to complete
- `when_any(tasks)` → `WhenAnyTask` — wait for first task to complete

### WorkflowActivityContext (`workflow_activity_context.py`)

Passed to activity functions as the first argument:

- `workflow_id` — the parent workflow's instance ID
- `task_id` — unique ID for this activity invocation

### RetryPolicy (`retry_policy.py`)

Retry configuration for activities and child workflows:

- `first_retry_interval: timedelta` — initial retry delay
- `max_number_of_attempts: int` — maximum retries (>= 1)
- `backoff_coefficient: Optional[float]` — exponential backoff multiplier (>= 1, default 1.0)
- `max_retry_interval: Optional[timedelta]` — maximum delay between retries
- `retry_timeout: Optional[timedelta]` — total time budget for retries

### WorkflowState / WorkflowStatus (`workflow_state.py`)

- `WorkflowStatus` enum: `UNKNOWN`, `RUNNING`, `COMPLETED`, `FAILED`, `TERMINATED`, `PENDING`, `SUSPENDED`, `STALLED`
- `WorkflowState`: wraps `OrchestrationState` with properties `instance_id`, `name`, `runtime_status`, `created_at`, `last_updated_at`, `serialized_input`, `serialized_output`, `serialized_custom_status`, `failure_details`

## How workflows execute

1. **Registration**: User decorates functions with `@wfr.workflow` / `@wfr.activity`. The runtime wraps them and stores them in the durabletask worker's registry.
2. **Startup**: `wfr.start()` opens a gRPC stream to the Dapr sidecar. The worker polls for work items.
3. **Scheduling**: Client calls `schedule_new_workflow(fn, input=...)`. The function's name (or `_dapr_alternate_name`) is sent to the backend.
4. **Execution**: The durabletask engine dispatches work items. Workflow functions are Python **generators** that `yield` tasks (activity calls, timers, child workflows). Activity functions are either sync (dispatched to the worker's thread pool) or `async def` (awaited directly on the worker's event loop). The engine records history; on replay, yielded tasks return cached results without re-executing.
5. **Determinism**: Workflows must be deterministic — no random, no wall-clock time, no I/O. Use `ctx.current_utc_datetime` instead of `datetime.now()`. Use `ctx.is_replaying` to guard side effects like logging.
6. **Completion**: Client polls via `wait_for_workflow_completion()` or `get_workflow_state()`.

## Naming and cross-app calls

- Default name: function's `__name__`
- Custom name: `@wfr.workflow(name='my_name')` or `@alternate_name('my_name')`
- Stored as `_dapr_alternate_name` attribute on the function
- Cross-app: pass activity/workflow name as a string + `app_id` parameter:
  ```python
  result = yield ctx.call_activity('remote_activity', input=data, app_id='other-app')
  ```

## Examples

Two example directories exercise workflows:

- **`examples/workflow/`** — primary, comprehensive examples:
  - `simple.py` — activities, retries, child workflows, external events, pause/resume
  - `task_chaining.py` — sequential activity chaining with error handling
  - `fan_out_fan_in.py` — parallel execution with `when_all()`
  - `human_approval.py` — external event waiting with timeouts
  - `monitor.py` — eternal polling workflow with `continue_as_new()`
  - `child_workflow.py` — child workflow orchestration
  - `cross-app1.py`, `cross-app2.py`, `cross-app3.py` — cross-app calls
  - `versioning.py` — workflow versioning with `is_patched()`
  - `simple_aio_client.py` — async client variant
  - `async_activities.py` — `async def` activities (HTTP fan-out with `httpx.AsyncClient`)

## Testing

Unit tests use mocks to simulate the durabletask layer (no Dapr runtime needed):

```bash
python -m unittest discover -v ./ext/dapr-ext-workflow/tests
```

Test patterns:
- **Mock classes**: `FakeTaskHubGrpcClient`, `FakeAsyncTaskHubGrpcClient`, `FakeOrchestrationContext`, `FakeActivityContext` — simulate durabletask responses without a real gRPC connection
- **Registration tests**: verify decorator behavior, custom naming, duplicate prevention
- **Client tests**: verify schedule/query/pause/resume/terminate round-trips
- **Async tests**: use `unittest.IsolatedAsyncioTestCase`
- **Worker readiness tests**: verify `start()` waits for gRPC stream, timeout behavior

## Environment variables

The extension resolves the Dapr sidecar address from (in order of precedence):
- Constructor `host`/`port` parameters
- `DAPR_GRPC_ENDPOINT` — full gRPC endpoint (overrides host:port)
- `DAPR_RUNTIME_HOST` (default `127.0.0.1`) + `DAPR_GRPC_PORT` (default `50001`)
- `DAPR_API_TOKEN` — optional authentication token (from `dapr.conf.settings`)

## Gotchas

- **Sync + async parity**: The sync client (`dapr_workflow_client.py`) and async client (`aio/dapr_workflow_client.py`) must stay in sync. Any new client method needs both variants.
- **Determinism**: Workflow functions are replayed from history. Non-deterministic code (random, datetime.now, I/O) inside a workflow function will break replay. Only activities can have side effects.
- **Generator pattern**: Workflow functions are generators that `yield` tasks. The return value is the workflow output. Do not use `await` — use `yield`.
- **Naming matters**: The name used to register a workflow/activity must match the name used to schedule it. Custom names via `@alternate_name` or `name=` parameter are stored as function attributes.
- **durabletask is vendored**: The underlying engine lives in `_durabletask/` inside this extension. Do not import it from outside `dapr.ext.workflow`.
- **Deprecated core methods**: Do not add new workflow functionality to `DaprClient` in the core SDK. Use the extension's `DaprWorkflowClient` instead.
- **Double registration guard**: Functions decorated with `@wfr.workflow` or `@wfr.activity` get `_workflow_registered` / `_activity_registered` attributes set to `True`. Attempting to re-register raises an error.
