"""
Copyright 2026 The Dapr Authors
Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at
    http://www.apache.org/licenses/LICENSE-2.0
Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
"""

from __future__ import annotations

from typing import Optional, Sequence

from dapr.ext.databricks._typing import InstanceIdFactory, RowMapper
from dapr.ext.databricks.batch_handler import DaprWorkflowBatchHandler
from dapr.ext.databricks.config import WorkflowSinkConfig


def _pipelines_module():
    """Lazily imports ``pyspark.pipelines``, with a clear error outside Lakeflow.

    ``pyspark.pipelines`` is provided by the Databricks Lakeflow (Spark
    Declarative Pipelines) runtime, not by a plain ``pip install pyspark``.
    Importing it at module scope would either force every ``dapr`` user to
    have a compatible pyspark on their path, or fail import of this whole
    extension outside a Lakeflow pipeline — so the import happens here,
    on first use, instead.
    """
    try:
        from pyspark import pipelines
    except ImportError as error:
        raise ImportError(
            'Databricks Lakeflow support requires pyspark.pipelines.foreach_batch_sink. '
            'Run this integration inside a supported Databricks Lakeflow pipeline.'
        ) from error
    return pipelines


def register_workflow_sink(
    name: str,
    workflow: str,
    *,
    id_field: Optional[str] = None,
    id_fields: Optional[Sequence[str]] = None,
    namespace: str = 'default',
    generation: str = 'v1',
    input_mapper: Optional[RowMapper] = None,
    instance_id_factory: Optional[InstanceIdFactory] = None,
    metadata: bool = True,
    max_in_flight: int = 8,
    max_records_per_batch: Optional[int] = None,
    host: Optional[str] = None,
    port: Optional[str] = None,
) -> DaprWorkflowBatchHandler:
    """Registers a Lakeflow sink that schedules a Dapr Workflow for each streaming record.

    Internally registers a ``pyspark.pipelines.foreach_batch_sink`` named
    ``name``; reference it as a flow ``target`` the same way you would any
    other sink:

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

    This only waits for Dapr to durably accept each workflow instance, not
    for the workflow to finish — the whole point is to decouple fast
    streaming ingestion from potentially long-running business processes.
    See ``dapr/ext/databricks/AGENTS.md`` (or the extension README) for the
    full delivery-semantics and full-refresh writeup; the summary:

    - Instance IDs are derived deterministically from ``namespace``, `name`,
      ``generation``, and the record's business key — never randomly — so a
      Lakeflow retry of a micro-batch recognizes work it already handed off
      instead of scheduling a duplicate execution.
    - This is retry-safe, not exactly-once: it depends on Dapr's workflow
      instance/history retention. Once a workflow instance is purged, its ID
      is no longer recognized as "already handled".
    - ``batch_id`` resets to 0 on a full pipeline refresh, so it is never
      used alone as identity. Bump ``generation`` to intentionally replay
      business actions after a full refresh; leave it unchanged for normal
      retries to keep deduplicating correctly.

    Args:
        name: Unique sink name within the pipeline (passed to
            ``foreach_batch_sink``).
        workflow: Registered Dapr Workflow name to schedule for each record.
        id_field: Row column to use as the business key. Mutually exclusive
            with ``id_fields`` and ``instance_id_factory``.
        id_fields: Row columns to combine into a composite business key.
            Mutually exclusive with ``id_field`` and ``instance_id_factory``.
        namespace: Logical partition for this sink's workflow identities
            (e.g. a business domain). Part of the deterministic instance ID.
        generation: Identity epoch, also part of the deterministic instance
            ID. Keep stable across normal retries; change it to deliberately
            replay business actions (e.g. after a full pipeline refresh).
            Defaults to ``'v1'`` so normal operation never accidentally
            replays already-handled records.
        input_mapper: Optional ``Row -> dict`` mapper for workflow input.
            Defaults to a JSON-safe ``Row.asDict(recursive=True)``.
        instance_id_factory: Escape hatch: ``(row, batch_id) -> str``
            computing the business-key component directly. Still namespaced
            by ``namespace``/``name``/``generation`` and sanitized like any
            other business key. Mutually exclusive with ``id_field`` and
            ``id_fields``.
        metadata: When ``True`` (default), wraps workflow input as
            ``{'data': <mapped row>, 'metadata': {...sink/workflow/batch/namespace/generation...}}``.
            When ``False``, the workflow input is exactly the mapped row,
            with no wrapper.
        max_in_flight: Maximum concurrent ``schedule_new_workflow`` calls per
            micro-batch.
        max_records_per_batch: Optional hard cap on records processed per
            micro-batch. Exceeding it fails the batch outright (see
            ``DaprWorkflowBatchHandler.process``) rather than silently
            dropping records — this integration targets business-action
            streams, not bulk data replication.
        host: Dapr sidecar/endpoint gRPC host. Defaults to the standard Dapr
            SDK environment/settings resolution (``DAPR_GRPC_ENDPOINT``,
            ``DAPR_RUNTIME_HOST``). Must be network-reachable from the
            Databricks compute running the pipeline.
        port: Dapr sidecar/endpoint gRPC port. Defaults to
            ``DAPR_GRPC_PORT``.

    Returns:
        The ``DaprWorkflowBatchHandler`` backing the registered sink, for
        advanced use (e.g. sharing it, or calling ``.close()`` explicitly).

    Raises:
        SinkConfigurationError: Invalid configuration (e.g. more than one of
            ``id_field``/``id_fields``/``instance_id_factory`` given).
        ImportError: Called outside a Databricks Lakeflow pipeline.
    """
    pipelines = _pipelines_module()

    config = WorkflowSinkConfig(
        name=name,
        workflow=workflow,
        id_field=id_field,
        id_fields=id_fields,
        namespace=namespace,
        generation=generation,
        input_mapper=input_mapper,
        instance_id_factory=instance_id_factory,
        metadata=metadata,
        max_in_flight=max_in_flight,
        max_records_per_batch=max_records_per_batch,
        host=host,
        port=port,
    )
    handler = DaprWorkflowBatchHandler(config)

    @pipelines.foreach_batch_sink(name=name)
    def _dapr_workflow_sink(df, batch_id):
        handler.process(df, batch_id)

    return handler
