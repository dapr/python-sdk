# dapr.ext.databricks

Turns records emitted by a Databricks Lakeflow streaming pipeline into durable Dapr Workflow
executions.

```text
Databricks Lakeflow
       │
       │ streaming records
       ▼
Dapr Databricks Sink
       │
       ▼
Dapr Workflow
       │
  ┌────┼──────────────┐
  ▼    ▼              ▼
 APIs  SaaS          Humans
       systems
```

```sh
pip install "dapr[databricks]"
```

## Why this exists

External side effects (freezing a card, calling a partner API, opening a case for a human to
review) have fundamentally different reliability requirements than transformations inside a
data pipeline. Instead of writing that business logic directly inside `foreach_batch_sink`,
hand the record to a Dapr Workflow and let it continue independently — with retries, timers,
human-in-the-loop waits, and crash recovery, all outside the streaming query's lifetime.

## Quick start

```python
from pyspark import pipelines as dp
from dapr.ext.databricks import register_workflow_sink

register_workflow_sink(
    name='order_actions',
    workflow='process_order',
    id_field='order_id',
    namespace='orders',
)

@dp.append_flow(target='order_actions', name='order_actions_flow')
def order_actions_flow():
    return spark.readStream.table('validated_orders')
```

`register_workflow_sink` registers the `foreach_batch_sink` for you — you do not write one by
hand for the standard case. See `examples/databricks/` in this repository for a complete,
runnable (no Databricks needed) fraud-remediation walkthrough.

### Custom input mapping

```python
register_workflow_sink(
    name='customer_actions',
    workflow='process_customer',
    id_field='customer_id',
    input_mapper=lambda row: {'customer': row['customer_id'], 'status': row['status']},
)
```

Without `input_mapper`, each row becomes a JSON-safe dict via `Row.asDict(recursive=True)`
(datetimes/dates -> ISO 8601 strings, `Decimal` -> string to avoid precision loss, bytes ->
base64).

### Composite keys and the escape hatch

```python
register_workflow_sink(
    name='transfers',
    workflow='process_transfer',
    id_fields=['account_id', 'transaction_id'],
)

# Or, for full control over how the business key is computed:
register_workflow_sink(
    name='transfers',
    workflow='process_transfer',
    instance_id_factory=lambda row, batch_id: f"{row['account_id']}:{row['transaction_id']}",
)
```

`instance_id_factory` computes the business-key *component* — the result is still namespaced by
`namespace`/`name`/`generation` and sanitized like any other key, so it can't accidentally
disable the full-refresh safety net described below.

### Optional lower-level API

```python
from dapr.ext.databricks import DaprWorkflowBatchHandler, WorkflowSinkConfig

handler = DaprWorkflowBatchHandler(
    WorkflowSinkConfig(name='orders', workflow='process_order', id_field='order_id')
)

@dp.foreach_batch_sink(name='orders')
def orders_handler(df, batch_id):
    handler.process(df, batch_id)
```

Use this if you need to fold the handoff into a hand-written `foreach_batch_sink` (custom
pre/post-processing around the same batch). The high-level `register_workflow_sink` remains the
recommended path for everything else.

## Delivery semantics

```text
Lakeflow delivery
        +
deterministic workflow identity
        +
Dapr workflow persistence
        =
retry-safe handoff while workflow history is retained
```

Every workflow instance ID is derived deterministically —
`<namespace>-<sink>-<generation>-<business_key>` — **never** a random UUID. Before scheduling,
the sink checks whether that instance already exists; if so, the record is treated as already
handled. If not, it schedules, and treats Dapr's "instance already exists" rejection (a
concurrent scheduler winning a race, or this exact instance from a previous attempt) the same
way. If neither check can be completed (Dapr unavailable, a timeout, an auth failure, ...), the
whole micro-batch fails so Lakeflow retries it — the sink never reports success while some
record's fate is unknown.

This is **retry-safe, not exactly-once**: it depends on Dapr retaining that instance's
history/state. Once a workflow instance is purged, Dapr (and therefore this extension) can no
longer tell that its business key was already handled; scheduling it again would start a new
execution. Plan your workflow-history retention accordingly if you need this guarantee to hold
indefinitely.

### Full refresh

Lakeflow's `batch_id` restarts at `0` both for a brand-new stream and after a full pipeline
refresh — it is never, by itself, a safe uniqueness key. `generation` (default `'v1'`) is part
of the deterministic instance ID for exactly this reason: normal retries keep `generation`
unchanged and continue deduplicating correctly; if you deliberately want to replay business
actions after a full refresh, bump `generation` (e.g. to `'v2'`) to get a fresh identity space
on purpose. Nothing changes `generation` for you — an accidental full refresh must not silently
replay business actions.

## Observability

Each scheduling attempt logs one structured line via the standard `logging` module (logger
`dapr.ext.databricks.batch_handler`) with sink name, workflow name, instance ID, Lakeflow batch
ID, namespace, generation, whether the instance was newly scheduled or already existed, and
scheduling latency. Business record contents are never logged.

## Configuration reference

```python
register_workflow_sink(
    name='orders',                 # sink name (foreach_batch_sink name)
    workflow='process_order',     # registered Dapr Workflow name

    id_field='order_id',            # business key column (mutually exclusive with the two below)
    id_fields=None,                  # composite business key columns
    instance_id_factory=None,         # (row, batch_id) -> business-key component

    namespace='orders',                # identity partition; part of the instance ID
    generation='v1',                    # identity epoch; bump to replay after a full refresh

    input_mapper=None,                    # Row -> dict; defaults to a JSON-safe asDict()
    metadata=True,                          # wrap input as {'data': ..., 'metadata': {...}}

    max_in_flight=8,                          # bounded concurrent schedule_new_workflow calls
    max_records_per_batch=None,                 # optional hard cap; fails the batch, never truncates silently

    host=None, port=None,                         # Dapr endpoint; defaults to the standard SDK env/settings
)
```

See `dapr/ext/databricks/AGENTS.md` in this repository for the full architecture, the exact
retry/race scenarios this extension handles, and the reasoning behind the ID-sanitization
scheme.
