# AGENTS.md — dapr.ext.databricks

Turns records from a Databricks Lakeflow streaming pipeline into durable Dapr Workflow
executions. Databricks keeps doing what it's good at (ingestion, transformation, streaming
checkpoints, Lakeflow execution); Dapr Workflow takes over the business process a record
triggers (durable execution, retries, timers, human interaction, external systems).

## Source layout

```
dapr/ext/databricks/
├── __init__.py            # Public API exports
├── sink.py                 # register_workflow_sink() + lazy pyspark.pipelines import
├── batch_handler.py         # DaprWorkflowBatchHandler — the reusable low-level API
├── scheduling.py             # ensure_workflow_scheduled() — the dedup/retry-safety core
├── identity.py                # Deterministic instance-ID derivation + sanitization
├── mapping.py                  # default_row_mapper() — Row -> JSON-safe dict
├── config.py                    # WorkflowSinkConfig dataclass + validation
├── exceptions.py                 # DaprDatabricksError hierarchy
├── _typing.py                     # RowLike / BatchDataFrameLike Protocols (no pyspark import)
└── py.typed

tests/ext/databricks/
├── _fakes.py                # Shared test doubles (FakeRow, FakeDataFrame, FakeWorkflowClient, ...)
├── test_identity.py          # Deterministic IDs, sanitization, Unicode, hashing
├── test_mapping.py            # Default + custom row mappers
├── test_scheduling.py          # ensure_workflow_scheduled: new/existing/race/lost-response
├── test_batch_handler.py        # End-to-end batch processing, retry, concurrency, metadata
├── test_config.py                 # WorkflowSinkConfig validation
└── test_sink.py                    # register_workflow_sink + pyspark.pipelines wiring

tests/integration/test_databricks_sink.py   # Runs against a real Dapr sidecar (no Databricks needed)
examples/databricks/                          # Fraud-remediation example (see its own README)
```

Installed via the `databricks` extra: `pip install "dapr[databricks]"`. Like `workflow`, this
extra has **no third-party runtime dependencies** — see "Dependency design" below.

## Architecture

```
┌───────────────────────────────────────────────────────────┐
│ Databricks Lakeflow pipeline                               │
│   @dp.append_flow(target=<sink>) -> readStream              │
└──────────────────────────┬──────────────────────────────────┘
                            │ micro-batch (DataFrame, batch_id)
┌──────────────────────────▼──────────────────────────────────┐
│ register_workflow_sink()                                     │
│  - lazily imports pyspark.pipelines                           │
│  - registers @dp.foreach_batch_sink(name=...) wrapping         │
│    DaprWorkflowBatchHandler.process                             │
└──────────────────────────┬────────────────────────────────────┘
                            │
┌──────────────────────────▼────────────────────────────────────┐
│ DaprWorkflowBatchHandler.process(df, batch_id)                  │
│  - df.toLocalIterator(prefetchPartitions=True) — never .collect() │
│  - bounded concurrency via ThreadPoolExecutor(max_in_flight)        │
│  - per row: identity.py -> scheduling.py -> optional metadata wrap    │
│  - any unresolved row -> raises, failing the micro-batch               │
└──────────────────────────┬────────────────────────────────────────────┘
                            │
┌──────────────────────────▼────────────────────────────────────────────┐
│ scheduling.ensure_workflow_scheduled(client, workflow, instance_id, ...) │
│  1. get_workflow_state(instance_id) -> exists? already accepted, done      │
│  2. else schedule_new_workflow(...); ALREADY_EXISTS response -> also done    │
│  3. any other error propagates (auth, unavailable, timeout, throttling, ...)  │
└──────────────────────────┬──────────────────────────────────────────────────┘
                            │
                 dapr.ext.workflow.DaprWorkflowClient (existing, unmodified)
                            │
                      Dapr sidecar / endpoint (gRPC)
```

No new workflow engine, no new transport: this extension is entirely a scheduling and
identity layer on top of the existing `dapr.ext.workflow.DaprWorkflowClient`.

## Public API

```python
from dapr.ext.databricks import (
    register_workflow_sink,     # high-level: registers a foreach_batch_sink
    DaprWorkflowBatchHandler,   # low-level: reusable batch-processing handler
    WorkflowSinkConfig,        # typed config, if constructing a handler directly
    default_row_mapper,       # the default Row -> dict mapper
    DaprDatabricksError,     # base exception
    SinkConfigurationError, # bad register_workflow_sink() config
    MissingBusinessKeyError, # configured id_field/id_fields absent or null on a row
    DaprDatabricksSinkError, # a micro-batch could not be durably handed off
)
```

`register_workflow_sink(name, workflow, *, id_field=None, id_fields=None, namespace='default',
generation='v1', input_mapper=None, instance_id_factory=None, metadata=True, max_in_flight=8,
max_records_per_batch=None, host=None, port=None)` is the primary entry point. See its
docstring in `sink.py` for the full parameter reference — kept there rather than duplicated here
so it can't drift out of sync.

## Delivery semantics (read this before changing `identity.py` or `scheduling.py`)

This is the part of the extension that must stay correct under review; the rest is
straightforward plumbing.

**The property this extension provides:** retry-safe handoff while Dapr workflow
instance/history is retained. Concretely:

```
deterministic instance ID (namespace-sink-generation-business_key)
        +
check-then-schedule (scheduling.ensure_workflow_scheduled)
        +
Dapr rejecting a duplicate non-terminal instance ID
        =
a Lakeflow retry of the same micro-batch recognizes work it already
handed off, instead of scheduling a second execution
```

**What it is not:** strict exactly-once delivery to arbitrary downstream systems. It is
exactly-once-Dapr-workflow-*scheduling* per `(namespace, sink, generation, business_key)`,
for as long as that instance's history has not been purged. Never describe this as
exactly-once in docs/comments/log messages without that qualification.

**The three scenarios this must handle** (each has a dedicated test in
`test_scheduling.py` and/or `test_batch_handler.py` — do not remove test coverage for any
of them):

1. **Micro-batch retry after partial failure.** Batch has records A and B; A schedules,
   B fails. The batch raises (see below), Lakeflow retries. On retry, A's
   `get_workflow_state` finds it already exists (skipped, not re-scheduled); B schedules
   for the first time. Net result: exactly one workflow each.
2. **Lost response.** `schedule_new_workflow` durably succeeds on Dapr's side, but the
   client never observes success (timeout, connection drop). The attempt still raises
   (we cannot prove acceptance), the batch fails, Lakeflow retries. On retry,
   `get_workflow_state` finds the instance Dapr already accepted and skips scheduling.
3. **Concurrent duplicate race.** Two callers derive the same instance ID (e.g. two
   in-flight retries) and both see "absent" before either schedules. Both call
   `schedule_new_workflow`; Dapr accepts exactly one and rejects the other with a
   duplicate-instance error. `scheduling.is_duplicate_instance_error` recognizes that
   rejection and both callers report success.

**Why the "exists" check ignores workflow status.** `ensure_workflow_scheduled` treats
*any* existing instance (including a long-completed one) as "already handled" — it does
not re-schedule just because the prior run reached a terminal state. Dapr itself would
allow reusing a terminal instance ID; this extension deliberately does not, because the
business key already produced one execution in this generation and re-running it would
be exactly the accidental-duplicate-side-effect this extension exists to prevent. This is
also why `generation` exists at all (see below) — it is the only sanctioned way to get a
fresh identity space on purpose.

**Duplicate-instance detection is dual-signaled** (`scheduling.is_duplicate_instance_error`):
`grpc.StatusCode.ALREADY_EXISTS` first, then a case-insensitive `'already exists'` substring
match on the error details as a fallback. The Dapr Workflow HTTP API reference documents a
409 response with that phrase for this condition; matching on text in addition to the status
code follows the existing precedent in `DaprWorkflowClient.get_workflow_state`, which already
relies on message-text matching (`'no such instance exists'`) rather than a status code alone.

**The batch-level failure rule:** if any record's outcome cannot be established as either
newly-scheduled or already-durably-present, `DaprWorkflowBatchHandler.process` raises
`DaprDatabricksSinkError`, chaining the first underlying error. This is deliberate — a
`foreach_batch_sink` that swallows a partial failure would let Lakeflow believe the batch
succeeded while some records were silently never scheduled.

## Full-refresh semantics (`generation`)

Lakeflow's `batch_id` is **not** a globally unique event identity: `batch_id` restarts at 0
both for a fresh stream and after a full pipeline refresh (Databricks' own docs: "A `batch_id`
of `0` represents the start of a stream, or the beginning of a full refresh"). If instance IDs
were derived from `batch_id` alone, a full refresh would silently replay every business action.

`generation` (default `'v1'`) is part of the deterministic instance-ID template specifically to
make this safe by default: normal retries keep `generation` unchanged and dedupe correctly
against prior runs in the same generation; a user who *intentionally* wants to replay business
actions after a full refresh changes `generation` (e.g. to `'v2'`), which — combined with
`namespace` and the sink name — produces an entirely fresh identity space. Nothing about a full
refresh changes `generation` automatically; that is a deliberate, safe-by-default choice: an
accidental full refresh must not replay business actions just because Databricks reset its
checkpoint.

## ID derivation and sanitization (`identity.py`)

Template: `<namespace>-<sink>-<generation>-<business_key>`, or
`<namespace>-<sink>-<generation>-<batch_id>-<record_index>` when no business-key strategy is
configured (weaker guarantee — see its docstring caveat about relying on stable row ordering
across retries).

Business key source, in priority order (mutually exclusive; `WorkflowSinkConfig` rejects
configuring more than one): `instance_id_factory(row, batch_id)` > `id_field` > `id_fields`
(joined with `_`). All three still get namespaced by `namespace`/sink/`generation` and run
through the same sanitizer — `instance_id_factory` is an escape hatch for *how the business key
is computed*, not a bypass of the identity/generation safety net.

Sanitization (`sanitize_segment`): a segment that is already short (<= 80 chars) and matches
`[A-Za-z0-9_-]+` (Dapr's documented allowed instance-ID characters) passes through unchanged,
so ordinary business keys stay human-readable. Anything else — Unicode, punctuation, empty
strings, over-length values — is replaced by a SHA-256 hex digest of the *whole* segment.
Hashing the whole segment (rather than stripping/replacing individual bad characters) is
deliberate: a character-by-character transliteration can collide distinct inputs (ASCII-folding
would collapse many distinct non-Latin business keys to the same, near-empty output; stripping
would collide `"a/b"` and `"a-b"`). The final composed ID is also capped at 128 characters
(this extension's own conservative bound — Dapr does not publish a maximum) via the same
hash-the-whole-thing strategy, careful to never truncate away the hash suffix itself (which
would collide every record in a sink with a pathologically long namespace/sink/generation
prefix onto the same ID — see the comment in `derive_instance_id`).

## Spark execution model

`DaprWorkflowBatchHandler.process` iterates `df.toLocalIterator(prefetchPartitions=True)`,
never `df.collect()` — a micro-batch is never required to fit entirely in driver memory at
once. Concurrency is bounded by `max_in_flight` (a plain `ThreadPoolExecutor`, sized to that
many workers — no unbounded fan-out of scheduling calls). `max_records_per_batch`, when set, is
a hard fail-fast cap, not a silent truncation: exceeding it raises immediately (already-submitted
records finish first) so an operator notices a business-action sink got pointed at a bulk/
analytical stream, rather than quietly scheduling millions of workflows.

Everything in `process()` runs on the Spark **driver** (this is inherent to
`foreach_batch_sink`/`toLocalIterator`, not a choice this extension makes) — appropriate for
business-action streams (the intended use case), not bulk data replication.

**`toLocalIterator()` is not universally available.** Confirmed via a live end-to-end run
against real Databricks serverless Lakeflow compute: `df.toLocalIterator(prefetchPartitions=True)`
itself raised `Exception: toLocalIterator() is not supported when using file-based collect`
(a Spark Connect-backed-compute limitation, not anything this extension controls) —
synchronously, before any row was read. `DaprWorkflowBatchHandler._iter_rows` catches exactly
that message and falls back to a `collect()`, bounded by `max_records_per_batch` (via
`df.limit(max_records_per_batch + 1)`) when configured, and logs a warning either way — this
is a degraded-safety fallback, not a silent one. Any other exception from `toLocalIterator`
(a corrupt source table, an expired storage token, etc.) is not this fallback's concern and
propagates normally. **Set `max_records_per_batch` when running on compute where
`toLocalIterator` is unavailable** — without it, the fallback has no bound and behaves like a
plain `collect()`.

## Authentication and secrets

No new auth/TLS mechanism: `DaprWorkflowBatchHandler` constructs (or accepts) a
`dapr.ext.workflow.DaprWorkflowClient`, which resolves `DAPR_GRPC_ENDPOINT` /
`DAPR_RUNTIME_HOST` / `DAPR_GRPC_PORT` / `DAPR_API_TOKEN` exactly as every other workflow
client in this SDK does. Nothing in this extension logs a payload's business data by default —
structured log lines (see `batch_handler._process_row`) carry only sink/workflow/instance-id/
batch-id/namespace/generation/outcome/latency, never the row or workflow input itself.

## Dependency design

`pyspark.pipelines` is provided by the Databricks Lakeflow (Spark Declarative Pipelines)
runtime — it is not part of a plain `pip install pyspark`, and even where a `pyspark` package
is present, `pyspark.pipelines` may not be. So:

- The `databricks` extra in `pyproject.toml` is **empty**, like `workflow` — no pyspark
  dependency, on purpose.
- `sink.py` imports `pyspark.pipelines` lazily, inside `register_workflow_sink`, not at module
  scope. `dapr.ext.databricks` (and `DaprWorkflowBatchHandler`) import cleanly with zero pyspark
  installed; only calling `register_workflow_sink` outside a Lakeflow pipeline fails, with the
  message: *"Databricks Lakeflow support requires pyspark.pipelines.foreach_batch_sink. Run
  this integration inside a supported Databricks Lakeflow pipeline."*
- `_typing.py` defines `RowLike`/`BatchDataFrameLike` as structural `Protocol`s instead of
  importing `pyspark.sql.Row`/`DataFrame`, so signatures stay strongly typed without a pyspark
  import anywhere, including under `TYPE_CHECKING`. `pyproject.toml` still needs
  `[[tool.mypy.overrides]] module = ["pyspark.*"] ignore_missing_imports = true` for the one
  `from pyspark import pipelines` line inside `sink.py`'s lazy-import function.

## Testing

```bash
uv run pytest tests/ext/databricks/                 # unit tests, no pyspark/Databricks needed
uv run pytest tests/integration/test_databricks_sink.py   # against a real Dapr sidecar
uv run pytest tests/examples/test_databricks.py           # fraud-remediation example
```

All unit tests mock/fake three things (`tests/ext/databricks/_fakes.py`): `Row`/`DataFrame`
(`FakeRow`/`FakeDataFrame` — plain Python, no pyspark), the Dapr workflow client
(`FakeWorkflowClient` — an in-memory instance-exists/schedule simulator that models Dapr's
actual duplicate-instance rejection, including under real thread concurrency via a lock), and
`pyspark.pipelines` itself (`test_sink.py` injects a fake module via `sys.modules`, since
pyspark is never installed in this environment).

`BarrierSyncedWorkflowClient` (in `_fakes.py`) exists specifically to make the "concurrent
duplicate race" test deterministic — it holds every caller at the start of
`schedule_new_workflow` until all parties have arrived, so the race is guaranteed to occur
rather than depending on incidental thread-scheduling timing.

## Known limitations

- Not exactly-once to arbitrary downstream systems — see "Delivery semantics" above.
- The batch/record-index fallback identity (no business key configured) depends on Lakeflow
  redelivering the same rows in the same order on retry; this is generally true for a
  straightforward read-then-sink pipeline but is a materially weaker guarantee than a business
  key, and is documented as such rather than presented as equivalent.
- `max_records_per_batch` protects against runaway fan-out but does not itself rate-limit the
  Lakeflow source; pair it with upstream rate limiting (e.g. `maxFilesPerTrigger`/
  `maxBytesPerTrigger` on the source `readStream`) for real protection.
- Purging a workflow instance's history removes Dapr's record of "already handled" for that
  instance ID; retention/purge policy is the operator's responsibility, same as for any other
  Dapr Workflow usage.
- On compute where `toLocalIterator()` is unavailable (observed on Databricks serverless), the
  handler falls back to a `collect()` bounded only by `max_records_per_batch` — set that
  explicitly on such compute; see "Spark execution model" above.
