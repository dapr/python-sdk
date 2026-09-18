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

import logging
import time
from concurrent.futures import Future, ThreadPoolExecutor, as_completed
from typing import Any, Dict, Iterable, List, Optional

from dapr.ext.databricks._typing import BatchDataFrameLike, RowLike
from dapr.ext.databricks.config import WorkflowSinkConfig
from dapr.ext.databricks.exceptions import DaprDatabricksSinkError
from dapr.ext.databricks.identity import derive_instance_id, extract_business_key
from dapr.ext.databricks.scheduling import ensure_workflow_scheduled
from dapr.ext.workflow.dapr_workflow_client import DaprWorkflowClient

_logger = logging.getLogger(__name__)

# Observed on Databricks serverless / Spark Connect-backed compute:
# `df.toLocalIterator()` itself raises this, synchronously, before any row is
# read. Matching on this substring (rather than any exception at all) keeps
# genuinely unrelated failures — a corrupt source table, an expired ADLS
# token — propagating normally instead of being swallowed by the fallback.
_TO_LOCAL_ITERATOR_UNSUPPORTED_MARKER = 'toLocalIterator() is not supported'


class DaprWorkflowBatchHandler:
    """Schedules one Dapr Workflow execution per row of a Lakeflow micro-batch.

    This is the reusable, lower-level building block behind
    ``register_workflow_sink``. Most users should call that function
    instead; use this class directly only if you need to fold the handoff
    into a hand-written ``foreach_batch_sink`` (e.g. custom pre/post-processing
    around the same batch):

    ```python
    from pyspark import pipelines as dp
    from dapr.ext.databricks import DaprWorkflowBatchHandler, WorkflowSinkConfig

    handler = DaprWorkflowBatchHandler(
        WorkflowSinkConfig(name='orders', workflow='process_order', id_field='order_id')
    )

    @dp.foreach_batch_sink(name='orders')
    def orders_handler(df, batch_id):
        handler.process(df, batch_id)
    ```

    Only waits for Dapr to durably accept (or already hold) each workflow
    instance — never for the workflow itself to finish — so a micro-batch
    stays fast regardless of how long the triggered business process runs.
    """

    def __init__(
        self,
        config: WorkflowSinkConfig,
        *,
        workflow_client: Optional[DaprWorkflowClient] = None,
    ) -> None:
        """Creates a batch handler for one sink configuration.

        Args:
            config: The sink's configuration.
            workflow_client: An existing client to reuse — e.g. a test fake,
                or one client shared across multiple sinks. When omitted, a
                new ``DaprWorkflowClient`` is created from ``config.host``/
                ``config.port``, falling back to the standard Dapr SDK
                environment/settings (``DAPR_GRPC_ENDPOINT``, ``DAPR_RUNTIME_HOST``,
                ``DAPR_GRPC_PORT``, ``DAPR_API_TOKEN``). This is the same
                resolution used everywhere else in ``dapr.ext.workflow``, so
                it works whether Dapr is a local sidecar or a
                network-accessible endpoint (e.g. a managed Dapr deployment)
                — Databricks compute is not expected to have a sidecar
                running in-process.
        """
        self._config = config
        self._owns_client = workflow_client is None
        self._client = workflow_client or DaprWorkflowClient(host=config.host, port=config.port)

    def process(self, df: BatchDataFrameLike, batch_id: int) -> None:
        """Schedules one Dapr Workflow execution per row in this micro-batch.

        Bounded by ``max_in_flight`` concurrent scheduling calls, iterating
        ``df`` via ``toLocalIterator()`` rather than ``collect()`` so a
        micro-batch never has to fit entirely in driver memory at once.

        If any record's outcome cannot be established as either newly
        scheduled or already durably present, this raises so the
        ``foreach_batch_sink`` call fails and Lakeflow retries the whole
        micro-batch. Records already durably accepted in this same attempt
        are unaffected by that retry: their deterministic instance IDs make
        them idempotent to re-process.

        Args:
            df: The micro-batch DataFrame Lakeflow passes to
                ``foreach_batch_sink``.
            batch_id: The Lakeflow micro-batch ID. Note that this resets to 0
                on a full pipeline refresh — see ``config.generation`` for
                how this extension avoids treating that as a fresh identity
                space by accident.

        Raises:
            DaprDatabricksSinkError: One or more records could not be
                durably scheduled, or the batch exceeded
                ``max_records_per_batch``.
        """
        limit = self._config.max_records_per_batch
        record_count = 0
        failures: List[Exception] = []

        with ThreadPoolExecutor(max_workers=self._config.max_in_flight) as pool:
            futures: Dict[Future, int] = {}
            for record_index, row in enumerate(self._iter_rows(df)):
                if limit is not None and record_index >= limit:
                    raise DaprDatabricksSinkError(
                        f"batch {batch_id} for sink '{self._config.name}' has more than "
                        f'max_records_per_batch={limit} records. dapr.ext.databricks is '
                        'designed for business-action streams, not bulk data replication; '
                        'add upstream rate limiting (e.g. maxFilesPerTrigger/'
                        'maxBytesPerTrigger on the source readStream), or raise '
                        'max_records_per_batch if this volume is intentional.'
                    )
                record_count += 1
                future = pool.submit(self._process_row, row, batch_id, record_index)
                futures[future] = record_index

            for future in as_completed(futures):
                try:
                    future.result()
                except Exception as error:
                    failures.append(error)

        if failures:
            raise DaprDatabricksSinkError(
                f'{len(failures)}/{record_count} record(s) in batch {batch_id} for sink '
                f"'{self._config.name}' could not be durably scheduled; failing the "
                'micro-batch so Lakeflow retries it.'
            ) from failures[0]

    def _iter_rows(self, df: BatchDataFrameLike) -> Iterable[RowLike]:
        """Iterates ``df`` memory-safely, falling back to a bounded ``collect()``
        where ``toLocalIterator`` itself is unavailable.

        Some compute (observed on Databricks serverless / Spark Connect-backed
        execution) raises directly from the ``toLocalIterator()`` call itself
        — before any row is read — with "not supported when using file-based
        collect". Nothing has been processed yet at that point, so falling
        back is safe. The fallback still respects ``max_records_per_batch``
        as a hard cap via ``limit()`` when configured; without that cap it
        logs a warning and collects the whole batch, since there is no other
        memory-safe primitive to fall back to on such compute.
        """
        try:
            return df.toLocalIterator(prefetchPartitions=True)
        except Exception as error:
            if _TO_LOCAL_ITERATOR_UNSUPPORTED_MARKER not in str(error):
                raise

        limit = self._config.max_records_per_batch
        if limit is None:
            _logger.warning(
                'dapr.ext.databricks: toLocalIterator() is unavailable in this Spark '
                'environment; falling back to collect() with no record limit. Set '
                'max_records_per_batch to bound driver memory use here.'
            )
            bounded_df = df
        else:
            _logger.warning(
                'dapr.ext.databricks: toLocalIterator() is unavailable in this Spark '
                'environment; falling back to a collect() bounded by '
                'max_records_per_batch=%s.',
                limit,
            )
            bounded_df = df.limit(limit + 1)
        return iter(bounded_df.collect())

    def close(self) -> None:
        """Closes the underlying Dapr Workflow client, if this handler created it."""
        if self._owns_client:
            self._client.close()

    def _process_row(self, row: RowLike, batch_id: int, record_index: int) -> None:
        start = time.monotonic()
        try:
            business_key = extract_business_key(
                row,
                batch_id,
                id_field=self._config.id_field,
                id_fields=self._config.id_fields,
                instance_id_factory=self._config.instance_id_factory,
            )
            instance_id = derive_instance_id(
                namespace=self._config.namespace,
                sink_name=self._config.name,
                generation=self._config.generation,
                business_key=business_key,
                batch_id=batch_id,
                record_index=record_index,
            )
            payload = self._build_payload(row, batch_id, instance_id)
            outcome = ensure_workflow_scheduled(
                self._client, self._config.workflow, instance_id, payload
            )
        except Exception:
            _logger.exception(
                'dapr.ext.databricks: sink=%s workflow=%s batch_id=%s record_index=%s '
                'failed to durably schedule workflow',
                self._config.name,
                self._config.workflow,
                batch_id,
                record_index,
            )
            raise

        latency_ms = (time.monotonic() - start) * 1000
        _logger.info(
            'dapr.ext.databricks: sink=%s workflow=%s instance_id=%s batch_id=%s '
            'namespace=%s generation=%s outcome=%s latency_ms=%.1f',
            self._config.name,
            self._config.workflow,
            instance_id,
            batch_id,
            self._config.namespace,
            self._config.generation,
            'newly_scheduled' if outcome.newly_scheduled else 'already_existed',
            latency_ms,
        )

    def _build_payload(self, row: RowLike, batch_id: int, instance_id: str) -> Any:
        data = self._config.row_mapper(row)
        if not self._config.metadata:
            return data
        return {
            'data': data,
            'metadata': {
                'sink': self._config.name,
                'workflow': self._config.workflow,
                'batch_id': batch_id,
                'namespace': self._config.namespace,
                'generation': self._config.generation,
            },
        }
