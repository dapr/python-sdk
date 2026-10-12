# -*- coding: utf-8 -*-
# Copyright 2026 The Dapr Authors
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#     http://www.apache.org/licenses/LICENSE-2.0
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Fraud remediation: the Dapr Workflow side of the dapr.ext.databricks example.

    Databricks Lakeflow identifies a suspicious transaction
                    |
             dapr.ext.databricks sink
                    |
            FraudRemediationWorkflow  <-- this file
                    |
      freeze card -> notify customer -> open investigation
                    |
             wait for analyst decision
                    |
                resolve case

This file is runnable on its own via `dapr run` (see the README in this
directory) and does not require Databricks or pyspark: it simulates a small
Lakeflow micro-batch in-process using `DaprWorkflowBatchHandler` directly,
the same reusable building block `register_workflow_sink` uses internally.
`fraud_remediation_pipeline.py`, alongside this file, shows the real
`pyspark.pipelines` wiring you'd use inside an actual Databricks Lakeflow
pipeline instead of this simulation.
"""

import logging
import threading
import time
from datetime import timedelta
from typing import Any, Dict, Iterator

import dapr.ext.workflow as wf
from dapr.ext.databricks import DaprWorkflowBatchHandler, WorkflowSinkConfig

wfr = wf.WorkflowRuntime()

ANALYST_DECISION_EVENT = 'analyst_decision'
ANALYST_TIMEOUT = timedelta(seconds=20)


@wfr.workflow(name='fraud_remediation')
def fraud_remediation_workflow(ctx: wf.DaprWorkflowContext, envelope: Dict[str, Any]):
    # register_workflow_sink's default `metadata=True` wraps the mapped row as
    # {'data': ..., 'metadata': {'sink', 'workflow', 'batch_id', 'namespace',
    # 'generation'}}, so the workflow can see which Lakeflow sink/batch/
    # generation triggered it without that bookkeeping polluting `data`, which
    # stays exactly what `input_mapper` (or the default row mapper) produced.
    transaction = envelope['data']
    if not ctx.is_replaying:
        print(
            f"*** Triggered by sink '{envelope['metadata']['sink']}', "
            f'batch {envelope["metadata"]["batch_id"]}'
        )

    yield ctx.call_activity(freeze_card, input=transaction)
    yield ctx.call_activity(notify_customer, input=transaction)
    case_id = yield ctx.call_activity(open_investigation, input=transaction)

    decision_event = ctx.wait_for_external_event(ANALYST_DECISION_EVENT)
    timeout_event = ctx.create_timer(ANALYST_TIMEOUT)
    winner = yield wf.when_any([decision_event, timeout_event])
    decision = decision_event.get_result() if winner == decision_event else 'ESCALATED_NO_RESPONSE'

    yield ctx.call_activity(resolve_case, input={'case_id': case_id, 'decision': decision})
    return {'case_id': case_id, 'decision': decision}


@wfr.activity(name='freeze_card')
def freeze_card(_, transaction: Dict[str, Any]) -> None:
    print(
        f'*** Freezing card for transaction {transaction["transaction_id"]} '
        f'(customer {transaction["customer_id"]})'
    )


@wfr.activity(name='notify_customer')
def notify_customer(_, transaction: Dict[str, Any]) -> None:
    print(f'*** Notifying customer {transaction["customer_id"]} about the frozen card')


@wfr.activity(name='open_investigation')
def open_investigation(_, transaction: Dict[str, Any]) -> str:
    case_id = f'CASE-{transaction["transaction_id"]}'
    print(f'*** Opened investigation {case_id}')
    return case_id


@wfr.activity(name='resolve_case')
def resolve_case(_, resolution: Dict[str, Any]) -> None:
    print(f'*** Resolved {resolution["case_id"]}: {resolution["decision"]}')


class _SimulatedLakeflowRow:
    """Stands in for a `pyspark.sql.Row` so this example runs without pyspark.

    A real Lakeflow micro-batch delivers actual `pyspark.sql.Row` objects;
    `DaprWorkflowBatchHandler` only ever calls `asDict()`/`__getitem__` on
    them (see `dapr.ext.databricks._typing.RowLike`), so this minimal stand-in
    is enough to demonstrate the real code path end-to-end.
    """

    def __init__(self, **fields: Any) -> None:
        self._fields = fields

    def asDict(self, recursive: bool = False) -> Dict[str, Any]:
        return dict(self._fields)

    def __getitem__(self, key: str) -> Any:
        return self._fields[key]


class _SimulatedLakeflowBatch:
    """Stands in for a `pyspark.sql.DataFrame` micro-batch; see the class above."""

    def __init__(self, rows) -> None:
        self._rows = rows

    def toLocalIterator(self, prefetchPartitions: bool = False) -> Iterator[Any]:
        return iter(self._rows)


def _instance_id_for(transaction_id: str) -> str:
    """The same deterministic template `dapr.ext.databricks` derives internally:
    `<namespace>-<sink>-<generation>-<business_key>`. Recomputing it here (rather
    than importing the internal `identity` module) is exactly what the
    documented, stable ID scheme is for: callers can predict an instance ID
    without having scheduled it themselves.
    """
    return f'fraud-fraud_actions-v1-{transaction_id}'


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO, format='%(message)s')

    wfr.start()
    wfr.wait_for_worker_ready()

    handler = DaprWorkflowBatchHandler(
        WorkflowSinkConfig(
            name='fraud_actions',
            workflow='fraud_remediation',
            id_field='transaction_id',
            namespace='fraud',
        )
    )

    detected_fraud_batch = [
        _SimulatedLakeflowRow(transaction_id='T-1001', customer_id='C-1', amount=4200.00),
        _SimulatedLakeflowRow(transaction_id='T-1002', customer_id='C-2', amount=999.50),
    ]

    # Best-effort cleanup so re-running this demo script against the same
    # Dapr instance behaves like a fresh run instead of finding yesterday's
    # instances "already existed". A real Lakeflow pipeline would never do
    # this -- reusing an instance ID on purpose is exactly the durable-history
    # dependency this extension documents (see the README/AGENTS.md).
    wf_client = wf.DaprWorkflowClient()
    for row in detected_fraud_batch:
        try:
            wf_client.purge_workflow(_instance_id_for(row['transaction_id']))
        except Exception:
            pass

    # This call only waits for Dapr to durably accept each workflow instance
    # -- not for fraud_remediation_workflow to finish running. It returns as
    # soon as scheduling is confirmed, which is what keeps a real Lakeflow
    # micro-batch fast regardless of how long remediation takes.
    print('*** Lakeflow micro-batch 1: scheduling fraud remediation workflows')
    handler.process(_SimulatedLakeflowBatch(detected_fraud_batch), batch_id=1)
    print('*** Micro-batch 1 handed off; each workflow now runs independently')

    # Simulates Lakeflow retrying the exact same micro-batch (e.g. after a
    # worker restart). Deterministic instance IDs mean this must not start a
    # second remediation for either transaction.
    print('*** Simulating a Lakeflow retry of the same micro-batch')
    handler.process(_SimulatedLakeflowBatch(detected_fraud_batch), batch_id=1)
    print('*** Retry complete: no duplicate workflow executions were created')

    def _resolve_after_delay() -> None:
        time.sleep(2)
        for row in detected_fraud_batch:
            wf_client.raise_workflow_event(
                _instance_id_for(row['transaction_id']),
                ANALYST_DECISION_EVENT,
                data='CONFIRMED_FRAUD',
            )

    threading.Thread(target=_resolve_after_delay, daemon=True).start()

    for row in detected_fraud_batch:
        instance_id = _instance_id_for(row['transaction_id'])
        state = wf_client.wait_for_workflow_completion(instance_id, timeout_in_seconds=30)
        if state and state.runtime_status.name == 'COMPLETED':
            print(f'*** Workflow {instance_id} completed: {state.serialized_output}')
        else:
            status = state.runtime_status.name if state else 'NOT_FOUND'
            print(f'*** Workflow {instance_id} ended with status: {status}')

    wf_client.close()
    handler.close()
    wfr.shutdown()
