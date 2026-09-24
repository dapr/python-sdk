# Databricks Lakeflow -> Dapr Workflow: fraud remediation

Demonstrates `dapr.ext.databricks`: turning records from a Databricks Lakeflow
streaming pipeline into durable Dapr Workflow executions.

```text
Databricks Lakeflow identifies a suspicious transaction
                |
         dapr.ext.databricks sink
                |
        FraudRemediationWorkflow
                |
  freeze card -> notify customer -> open investigation
                |
         wait for analyst decision
                |
            resolve case
```

## Files

- **`fraud_remediation_workflow.py`** -- the Dapr Workflow side: the
  `fraud_remediation` workflow and its activities (freeze card, notify
  customer, open investigation, wait for an analyst decision, resolve the
  case). Runnable locally via `dapr run`, no Databricks or pyspark required:
  its `__main__` block simulates a small Lakeflow micro-batch in-process
  using `DaprWorkflowBatchHandler` directly -- the same reusable building
  block `register_workflow_sink` uses internally -- and then retries the
  identical batch to demonstrate that no duplicate workflow executions are
  created.
- **`fraud_remediation_pipeline.py`** -- the Databricks Lakeflow side:
  `register_workflow_sink` plus the `@dp.append_flow` that feeds it. This
  file is illustrative only. It is not executed by this repository's test
  suite and cannot run locally -- it depends on `pyspark.pipelines` (provided
  by the Databricks Lakeflow runtime, not `pip install pyspark`), the
  implicit `spark` session Lakeflow injects into pipeline source files, and a
  Unity Catalog table named `detected_fraud`. Copy its pattern into an actual
  Databricks Lakeflow pipeline to wire this integration up for real.

See [`dapr/ext/databricks/README.md`](../../dapr/ext/databricks/README.md)
for the full public API, delivery-semantics, and full-refresh writeup.

## Prerequisites

- [Dapr CLI and initialized environment](https://docs.dapr.io/getting-started)
- [Install Python 3.10+](https://www.python.org/downloads/)
- `pip install "dapr[workflow,databricks]"` (this repo's dev environment
  already has both via `uv sync --all-packages --group dev`)

## Run the example

```sh
dapr run --app-id fraud-remediation-demo -- python3 fraud_remediation_workflow.py
```

Expected output (interleaved with Dapr/durabletask log lines):

```text
*** Lakeflow micro-batch 1: scheduling fraud remediation workflows
*** Micro-batch 1 handed off; each workflow now runs independently
*** Simulating a Lakeflow retry of the same micro-batch
*** Retry complete: no duplicate workflow executions were created
*** Triggered by sink 'fraud_actions', batch 1
*** Freezing card for transaction T-1001 (customer C-1)
*** Notifying customer C-1 about the frozen card
*** Opened investigation CASE-T-1001
*** Resolved CASE-T-1001: CONFIRMED_FRAUD
*** Workflow fraud-fraud_actions-v1-T-1001 completed: {"case_id": "CASE-T-1001", "decision": "CONFIRMED_FRAUD"}
... (and the same for T-1002)
```

Look for the structured `dapr.ext.databricks: sink=... outcome=...` log
lines: the first micro-batch reports `outcome=newly_scheduled` for both
transactions, and the simulated retry reports `outcome=already_existed` for
both -- the same transaction never starts a second remediation workflow.

The example purges its two demo workflow instances on startup so repeated
local runs behave like a fresh run; a real Lakeflow pipeline would never do
this; see the "Delivery semantics" section of the extension README for why
reusing an instance ID on purpose depends on Dapr's workflow history
retention.

## Cleanup

```sh
dapr stop --app-id fraud-remediation-demo
```
