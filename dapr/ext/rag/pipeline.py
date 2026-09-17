# -*- coding: utf-8 -*-

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

# DurableRAGPipeline and its workflow orchestrator/activities.
#
# Every activity below is a thin `self._activity_*` method wrapped by a plain
# nested-function closure at registration time (see
# `_register_workflow_and_activities`), rather than registered directly as a
# bound method: `WorkflowRuntime` registration (and `DaprWorkflowContext.
# call_activity` when given a function rather than a string) can stamp a
# `_dapr_alternate_name` attribute onto the registered callable, and bound
# methods do not support arbitrary attribute assignment. Plain closures avoid
# the question entirely, matching how every example in this repo defines
# activities/workflows as plain functions. Every `call_activity`/
# `schedule_new_workflow` call below also passes the activity/workflow's
# *name* (a string) rather than a function object, which `DaprWorkflowContext`
# explicitly supports and sidesteps the same concern on the calling side.
#
# The orchestrator (`_orchestrate_ingestion`) is deterministic: it never
# performs I/O, reads the wall clock (it uses `ctx.current_utc_datetime`
# instead), or generates random values -- every one of those happens inside
# an activity. Documents are processed in bounded batches sized by
# `PipelineConfig.max_concurrent_documents`; after each batch the
# orchestrator calls `ctx.continue_as_new(...)` with a small, flat "cursor"
# state (`_IngestionState`) rather than accumulating the manifest or every
# batch's results in workflow history, so history size stays bounded
# regardless of corpus size (see `examples/workflow/monitor.py` for the same
# continue_as_new pattern applied to an eternal polling workflow).

from __future__ import annotations

import dataclasses
import json
import logging
import math
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from dapr.clients import DaprClient
from dapr.ext.rag._wire import from_wire, to_wire
from dapr.ext.rag.embedding.base import Embedder
from dapr.ext.rag.errors import (
    DocumentChangedError,
    NonRetryableError,
    RetryableError,
    VersionValidationError,
)
from dapr.ext.rag.fingerprints import (
    compute_chunk_id,
    compute_content_hash,
    compute_manifest_hash,
    compute_pipeline_fingerprint,
)
from dapr.ext.rag.models import (
    ActivationRecord,
    CompletionRecord,
    DocumentFailure,
    DocumentOutcome,
    DocumentOutcomeStatus,
    DocumentWorkItem,
    EmbedProgressRecord,
    FoundryIQKnowledgeSourceConfig,
    ManifestSummary,
    PipelineConfig,
    PipelineStage,
    PipelineStatus,
    ProvenanceRecord,
    SourceDocument,
    SourceMetadata,
    SourceProvider,
    ValidationResult,
    VectorRecord,
)
from dapr.ext.rag.parsing.base import DocumentParser
from dapr.ext.rag.sources.base import DocumentSource
from dapr.ext.rag.splitting import DocumentSplitter
from dapr.ext.rag.state import PipelineStateStore
from dapr.ext.rag.testing import FailureInjector
from dapr.ext.rag.vector_stores.base import VectorIndex
from dapr.ext.workflow import (
    DaprWorkflowClient,
    DaprWorkflowContext,
    RetryPolicy,
    WorkflowActivityContext,
    WorkflowRuntime,
    WorkflowState,
    WorkflowStatus,
)

logger = logging.getLogger(__name__)

_NON_TERMINAL_STATUSES = frozenset(
    {WorkflowStatus.RUNNING, WorkflowStatus.PENDING, WorkflowStatus.SUSPENDED}
)


@dataclasses.dataclass(frozen=True, slots=True)
class _IngestionState:
    """The ingestion orchestrator's entire input, carried across `continue_as_new`.

    Flat by necessity (see `_wire.py`) and deliberately small: the actual
    manifest and per-document results live in Dapr state, not here, so this
    never grows with corpus size no matter how many `continue_as_new`
    generations a large run goes through.
    """

    pipeline_id: str
    version: str
    activate_when_complete: bool
    fail_fast: bool
    page_size: int
    embedding_batch_size: int
    max_activity_attempts: int
    first_retry_interval_seconds: float
    backoff_coefficient: float
    max_retry_interval_seconds: float
    prefix: Optional[str] = None
    manifest_ready: bool = False
    total_documents: int = 0
    manifest_hash: str = ''
    cursor: int = 0


@dataclasses.dataclass(frozen=True, slots=True)
class _ActivationState:
    """Input for the standalone activation workflow (`DurableRAGPipeline.activate_version`)."""

    pipeline_id: str
    version: str


def _retry_policy_from(config: Any) -> RetryPolicy:
    """Builds a `RetryPolicy` from anything with the five retry-shaped fields.

    Works for both `PipelineConfig` and `_IngestionState`, which intentionally
    share these field names so this helper can serve both.
    """
    return RetryPolicy(
        first_retry_interval=timedelta(seconds=config.first_retry_interval_seconds),
        max_number_of_attempts=config.max_activity_attempts,
        backoff_coefficient=config.backoff_coefficient,
        max_retry_interval=timedelta(seconds=config.max_retry_interval_seconds),
    )


def _utcnow_iso() -> str:
    """Wall-clock timestamp for use inside activities. Never call from the orchestrator."""
    return datetime.now(timezone.utc).isoformat()


def _parse_iso(value: str) -> datetime:
    """Parses an ISO-8601 timestamp, treating a naive one as UTC.

    Activity-side timestamps (`_utcnow_iso`) are always timezone-aware;
    orchestrator-side ones (`ctx.current_utc_datetime.isoformat()`) may not
    be, depending on the durabletask engine's own convention. Normalizing
    here avoids a `TypeError` when subtracting one from the other.
    """
    parsed = datetime.fromisoformat(value)
    return parsed if parsed.tzinfo is not None else parsed.replace(tzinfo=timezone.utc)


class DurableRAGPipeline:
    """Durably ingests documents from a `DocumentSource` into a versioned `VectorIndex`.

    See `dapr/ext/rag/AGENTS.md` for the full architecture. In short: a Dapr
    Workflow orchestrator drives discovery, per-document processing (in
    bounded batches), validation, and activation; every step that performs
    I/O runs in a workflow activity, and per-document idempotency is tracked
    in Dapr state so a crash or a re-run resumes without re-embedding
    completed work.
    """

    def __init__(
        self,
        *,
        source: DocumentSource,
        parser: DocumentParser,
        splitter: DocumentSplitter,
        embedder: Embedder,
        vector_store: VectorIndex,
        state_store_name: str,
        pipeline_id: Optional[str] = None,
        config: Optional[PipelineConfig] = None,
        pubsub_name: Optional[str] = None,
        pubsub_topic: str = 'index.version.activated',
        foundry_iq_knowledge_source: Optional[FoundryIQKnowledgeSourceConfig] = None,
        workflow_runtime: Optional[WorkflowRuntime] = None,
        workflow_client: Optional[DaprWorkflowClient] = None,
        dapr_client: Optional[DaprClient] = None,
        failure_injector: Optional[FailureInjector] = None,
    ) -> None:
        """Initializes a DurableRAGPipeline.

        Args:
            source: Where to discover and download documents from.
            parser: Parses downloaded bytes into `Document`s.
            splitter: Splits `Document`s into `Chunk`s.
            embedder: Generates embeddings for chunk text.
            vector_store: The versioned vector index to write into.
            state_store_name: The Dapr state store component backing
                manifests, idempotency records, status, and the
                active-version pointer.
            pipeline_id: A stable identifier for this logical pipeline (used
                to namespace state keys and workflow/activity names).
                Defaults to `vector_store.target_index_name`.
            config: Tuning knobs; see `PipelineConfig`.
            pubsub_name: Optional Dapr pub/sub component to publish an
                `index.version.activated` event to after a successful
                activation. Publishing is best-effort: a failure is logged,
                not raised, so it never fails an otherwise-successful run.
            pubsub_topic: Topic to publish activation events to.
            foundry_iq_knowledge_source: Opt-in, off by default. When set,
                registers/updates a Foundry IQ search-index knowledge source
                for this pipeline's activated version, as a workflow activity
                chained strictly after activation succeeds. Requires
                `vector_store` to support it (currently only
                `AzureAISearchVectorStore`) -- see `docs/rag/foundry-iq.md`
                and `AzureAISearchVectorStore.register_foundry_iq_knowledge_
                source` for the full rationale and idempotency behavior.
                Registration is best-effort like `pubsub_name`: a failure is
                logged, not raised, so it never fails an otherwise-successful
                activation.
            workflow_runtime: A `WorkflowRuntime` to register the pipeline's
                orchestrator/activities on; a new one is created when
                omitted. Only `run_worker()` actually starts it, so
                constructing a pipeline is safe in a short-lived
                CLI/client process too.
            workflow_client: A `DaprWorkflowClient` to reuse; a new one is
                created (and owned/closed by this instance) when omitted.
            dapr_client: A `DaprClient` to reuse for state access; a new one
                is created (and owned/closed by this instance) when omitted.
            failure_injector: Test/demo-only hook to deliberately crash the
                process at a chosen point (see `testing.py`). Never set this
                outside a controlled demo or test.

        Raises:
            ValueError: `foundry_iq_knowledge_source` was given but
                `vector_store` has no `register_foundry_iq_knowledge_source`
                method.
        """
        if foundry_iq_knowledge_source is not None and not hasattr(
            vector_store, 'register_foundry_iq_knowledge_source'
        ):
            raise ValueError(
                'foundry_iq_knowledge_source requires a vector_store that supports it '
                f'(currently only AzureAISearchVectorStore); got {type(vector_store).__name__}.'
            )
        self._source = source
        self._parser = parser
        self._splitter = splitter
        self._embedder = embedder
        self._vector_store = vector_store
        self._pipeline_id = pipeline_id or vector_store.target_index_name
        self._config = config or PipelineConfig()
        self._pubsub_name = pubsub_name
        self._pubsub_topic = pubsub_topic
        self._foundry_iq_knowledge_source = foundry_iq_knowledge_source
        self._failure_injector = failure_injector or FailureInjector()

        self._owns_workflow_client = workflow_client is None
        self._workflow_client = workflow_client or DaprWorkflowClient()
        self._owns_dapr_client = dapr_client is None
        self._dapr_client = dapr_client or DaprClient()
        self._state = PipelineStateStore(
            state_store_name=state_store_name, dapr_client=self._dapr_client
        )
        self._workflow_runtime = workflow_runtime or WorkflowRuntime()

        self._pipeline_fingerprint = compute_pipeline_fingerprint(
            parser_config_hash=self._parser.config_fingerprint(),
            splitter_config_hash=self._splitter.config_fingerprint(),
            embedding_model=self._embedder.embedding_model,
            embedding_config_hash=self._embedder.config_fingerprint(),
        )

        self._orchestrator_name = f'rag_ingest__{self._pipeline_id}'
        self._activate_workflow_name = f'rag_activate__{self._pipeline_id}'
        self._activity_names = {
            'discover_and_manifest': f'rag_discover__{self._pipeline_id}',
            'get_manifest_batch': f'rag_get_batch__{self._pipeline_id}',
            'process_document': f'rag_process_document__{self._pipeline_id}',
            'validate_version': f'rag_validate__{self._pipeline_id}',
            'activate_version': f'rag_activate_version__{self._pipeline_id}',
            'publish_activation_event': f'rag_publish_activation__{self._pipeline_id}',
            'register_foundry_iq_knowledge_source': f'rag_foundry_iq__{self._pipeline_id}',
            'update_status': f'rag_update_status__{self._pipeline_id}',
        }
        self._register_workflow_and_activities()

    # -- process lifecycle --------------------------------------------------

    def run_worker(self, *, wait_for_ready: bool = True, timeout: float = 30.0) -> None:
        """Starts this pipeline's `WorkflowRuntime` worker.

        Call this in whichever process should execute the ingestion workflow
        and its activities (see `examples/rag/worker.py`); a short-lived
        client process that only calls `start()`/`get_status()`/etc. never
        needs to call this.
        """
        self._workflow_runtime.start()
        if wait_for_ready:
            self._workflow_runtime.wait_for_worker_ready(timeout=timeout)

    def shutdown_worker(self) -> None:
        """Stops this pipeline's `WorkflowRuntime` worker."""
        self._workflow_runtime.shutdown()

    def close(self) -> None:
        """Releases owned clients and adapter resources."""
        if self._owns_workflow_client:
            self._workflow_client.close()
        if self._owns_dapr_client:
            self._dapr_client.close()
        self._source.close()
        self._vector_store.close()

    # -- public API -----------------------------------------------------

    def start(
        self,
        *,
        version: str,
        activate_when_complete: bool = True,
        prefix: Optional[str] = None,
        instance_id: Optional[str] = None,
    ) -> str:
        """Starts (or resumes) an ingestion run for `version`.

        Uses a stable, deterministic instance ID by default
        (`rag-ingest-{pipeline_id}-{version}`), so calling `start()` again for
        a version whose run is still in flight returns that same instance
        rather than starting a second, conflicting one. Per
        `DaprWorkflowClient`, an instance ID can always be reused once the
        prior run reached a terminal state, which is how a fresh run after a
        prior failure begins -- idempotency then comes from the per-document
        completion records in Dapr state, not from the instance ID.

        Args:
            version: The logical index version to build (never the currently
                active one -- see `AGENTS.md` for why).
            activate_when_complete: Activate `version` automatically once it
                validates successfully.
            prefix: Overrides the source's configured prefix for this run.
            instance_id: Overrides the default stable instance ID.

        Returns:
            The workflow instance ID (whether newly scheduled, or already running).
        """
        resolved_instance_id = instance_id or self._stable_instance_id(version)
        existing = self._workflow_client.get_workflow_state(resolved_instance_id)
        if existing is not None and existing.runtime_status in _NON_TERMINAL_STATUSES:
            logger.info(
                'Ingestion for pipeline=%s version=%s is already running as %s; not starting '
                'a second run.',
                self._pipeline_id,
                version,
                resolved_instance_id,
            )
            return resolved_instance_id

        initial_state = _IngestionState(
            pipeline_id=self._pipeline_id,
            version=version,
            activate_when_complete=activate_when_complete,
            fail_fast=self._config.fail_fast,
            page_size=self._config.effective_manifest_page_size,
            embedding_batch_size=self._config.embedding_batch_size,
            max_activity_attempts=self._config.max_activity_attempts,
            first_retry_interval_seconds=self._config.first_retry_interval_seconds,
            backoff_coefficient=self._config.backoff_coefficient,
            max_retry_interval_seconds=self._config.max_retry_interval_seconds,
            prefix=prefix,
        )
        return self._workflow_client.schedule_new_workflow(
            self._orchestrator_name,
            input=to_wire(initial_state),
            instance_id=resolved_instance_id,
        )

    def activate_version(self, version: str, *, instance_id: Optional[str] = None) -> str:
        """Validates and activates an already-built version on its own.

        Runs the same validate-then-activate steps the main ingestion
        workflow runs at the end of a successful build, as a standalone
        workflow -- for activating a version built by an earlier run without
        rebuilding it.
        """
        resolved_instance_id = instance_id or f'rag-activate-{self._pipeline_id}-{version}'
        existing = self._workflow_client.get_workflow_state(resolved_instance_id)
        if existing is not None and existing.runtime_status in _NON_TERMINAL_STATUSES:
            return resolved_instance_id
        payload = _ActivationState(pipeline_id=self._pipeline_id, version=version)
        return self._workflow_client.schedule_new_workflow(
            self._activate_workflow_name,
            input=to_wire(payload),
            instance_id=resolved_instance_id,
        )

    def get_status(self, version: str) -> Optional[PipelineStatus]:
        """Reads the current status of an ingestion run for `version`, if any."""
        return self._state.read_status(pipeline_id=self._pipeline_id, version=version)

    def get_workflow_state(self, instance_id: str) -> Optional[WorkflowState]:
        """Reads the underlying workflow instance's raw state (status, timestamps, ...)."""
        return self._workflow_client.get_workflow_state(instance_id)

    def resolve_active_version(self) -> Optional[str]:
        """Returns this pipeline's currently-active version, or `None` if never activated."""
        record, _etag = self._state.read_activation(self._pipeline_id)
        return record.active_version if record is not None else None

    def _stable_instance_id(self, version: str) -> str:
        return f'rag-ingest-{self._pipeline_id}-{version}'

    # -- registration ------------------------------------------------------

    def _register_workflow_and_activities(self) -> None:
        names = self._activity_names

        def rag_ingest_orchestrator(ctx: DaprWorkflowContext, wf_input: dict):
            return (yield from self._orchestrate_ingestion(ctx, wf_input))

        def rag_activate_orchestrator(ctx: DaprWorkflowContext, wf_input: dict):
            return (yield from self._orchestrate_activation(ctx, wf_input))

        def discover_and_manifest(ctx: WorkflowActivityContext, raw: dict) -> dict:
            return self._activity_discover_and_manifest(ctx, raw)

        def get_manifest_batch(ctx: WorkflowActivityContext, raw: dict) -> dict:
            return self._activity_get_manifest_batch(ctx, raw)

        def process_document(ctx: WorkflowActivityContext, raw: dict) -> dict:
            return self._activity_process_document(ctx, raw)

        def validate_version(ctx: WorkflowActivityContext, raw: dict) -> dict:
            return self._activity_validate_version(ctx, raw)

        def activate_version(ctx: WorkflowActivityContext, raw: dict) -> dict:
            return self._activity_activate_version(ctx, raw)

        def publish_activation_event(ctx: WorkflowActivityContext, raw: dict) -> dict:
            return self._activity_publish_activation_event(ctx, raw)

        def register_foundry_iq_knowledge_source(ctx: WorkflowActivityContext, raw: dict) -> dict:
            return self._activity_register_foundry_iq_knowledge_source(ctx, raw)

        def update_status(ctx: WorkflowActivityContext, raw: dict) -> dict:
            return self._activity_update_status(ctx, raw)

        self._workflow_runtime.register_workflow(
            rag_ingest_orchestrator, name=self._orchestrator_name
        )
        self._workflow_runtime.register_workflow(
            rag_activate_orchestrator, name=self._activate_workflow_name
        )
        self._workflow_runtime.register_activity(
            discover_and_manifest, name=names['discover_and_manifest']
        )
        self._workflow_runtime.register_activity(
            get_manifest_batch, name=names['get_manifest_batch']
        )
        self._workflow_runtime.register_activity(process_document, name=names['process_document'])
        self._workflow_runtime.register_activity(validate_version, name=names['validate_version'])
        self._workflow_runtime.register_activity(activate_version, name=names['activate_version'])
        self._workflow_runtime.register_activity(
            publish_activation_event, name=names['publish_activation_event']
        )
        self._workflow_runtime.register_activity(
            register_foundry_iq_knowledge_source, name=names['register_foundry_iq_knowledge_source']
        )
        self._workflow_runtime.register_activity(update_status, name=names['update_status'])

    # -- orchestrators (deterministic: no I/O, no clock, no randomness) -----

    def _orchestrate_ingestion(self, ctx: DaprWorkflowContext, wf_input: dict):
        state = from_wire(wf_input, _IngestionState)
        retry_policy = _retry_policy_from(state)
        names = self._activity_names

        if not state.manifest_ready:
            summary_raw = yield ctx.call_activity(
                names['discover_and_manifest'],
                input={
                    'pipeline_id': state.pipeline_id,
                    'version': state.version,
                    'page_size': state.page_size,
                    'prefix': state.prefix,
                },
                retry_policy=retry_policy,
            )
            summary = from_wire(summary_raw, ManifestSummary)
            state = dataclasses.replace(
                state,
                manifest_ready=True,
                total_documents=summary.total_documents,
                manifest_hash=summary.manifest_hash,
            )
            yield ctx.call_activity(
                names['update_status'],
                input={
                    'pipeline_id': state.pipeline_id,
                    'version': state.version,
                    'workflow_instance_id': ctx.instance_id,
                    'total_documents': summary.total_documents,
                    'stage': PipelineStage.PROCESSING_DOCUMENTS.value,
                },
                retry_policy=retry_policy,
            )

        if state.cursor < state.total_documents:
            page_index = state.cursor // state.page_size
            batch_raw = yield ctx.call_activity(
                names['get_manifest_batch'],
                input={
                    'pipeline_id': state.pipeline_id,
                    'version': state.version,
                    'page_index': page_index,
                },
                retry_policy=retry_policy,
            )
            batch_items: list[dict] = batch_raw['items']

            # Every item is scheduled up front -- this *is* the fan-out, bounded to
            # at most `page_size` (== max_concurrent_documents) in-flight activities
            # at once. Each is then yielded individually (fan-in) rather than via
            # `when_all`, so one document's exhausted-retry failure doesn't prevent
            # collecting the others' results: `process_document` never raises for an
            # *expected* failure (see errors.py's module docstring), so an exception
            # here only ever means retries were exhausted or something truly
            # unexpected happened -- and every other task in the batch has already
            # run to completion (including recording its own state) by this point.
            tasks: dict[str, Any] = {}
            for ordinal, item in enumerate(batch_items):
                tasks[item['document_id']] = ctx.call_activity(
                    names['process_document'],
                    input={
                        'work_item': item,
                        'pipeline_id': state.pipeline_id,
                        'version': state.version,
                        'pipeline_fingerprint': self._pipeline_fingerprint,
                        'document_ordinal': state.cursor + ordinal,
                    },
                    retry_policy=retry_policy,
                )

            outcomes: list[DocumentOutcome] = []
            for document_id, task in tasks.items():
                try:
                    outcome_raw = yield task
                    outcomes.append(from_wire(outcome_raw, DocumentOutcome))
                except Exception as exc:
                    outcomes.append(
                        DocumentOutcome(
                            document_id=document_id,
                            status=DocumentOutcomeStatus.FAILED.value,
                            error_type=type(exc).__name__,
                            error_message=str(exc)[:500],
                            retryable=None,
                        )
                    )

            if not ctx.is_replaying:
                logger.info(
                    'pipeline=%s version=%s processed a batch of %d document(s) (cursor %d/%d)',
                    state.pipeline_id,
                    state.version,
                    len(batch_items),
                    state.cursor,
                    state.total_documents,
                )

            yield ctx.call_activity(
                names['update_status'],
                input={
                    'pipeline_id': state.pipeline_id,
                    'version': state.version,
                    'outcomes': [to_wire(o) for o in outcomes],
                },
                retry_policy=retry_policy,
            )

            any_failed = any(o.status == DocumentOutcomeStatus.FAILED.value for o in outcomes)
            if any_failed and state.fail_fast:
                final_raw = yield ctx.call_activity(
                    names['update_status'],
                    input={
                        'pipeline_id': state.pipeline_id,
                        'version': state.version,
                        'stage': PipelineStage.FAILED.value,
                        'completed_at': ctx.current_utc_datetime.isoformat(),
                    },
                    retry_policy=retry_policy,
                )
                return final_raw

            state = dataclasses.replace(state, cursor=state.cursor + len(batch_items))
            ctx.continue_as_new(to_wire(state))
            return None

        # Every document has been processed (or none existed) -- validate, then
        # activate only if validation passed.
        validation_raw = yield ctx.call_activity(
            names['validate_version'],
            input={
                'pipeline_id': state.pipeline_id,
                'version': state.version,
                'expected_documents': state.total_documents,
            },
            retry_policy=retry_policy,
        )
        validation = from_wire(validation_raw, ValidationResult)

        active_version: Optional[str] = None
        activation_succeeded = False
        if validation.valid and state.activate_when_complete:
            activation_raw = yield ctx.call_activity(
                names['activate_version'],
                input={
                    'pipeline_id': state.pipeline_id,
                    'version': state.version,
                    'manifest_hash': state.manifest_hash,
                    'workflow_instance_id': ctx.instance_id,
                },
                retry_policy=retry_policy,
            )
            activation_succeeded = True
            active_version = activation_raw['active_version']
            yield ctx.call_activity(
                names['register_foundry_iq_knowledge_source'],
                input={'pipeline_id': state.pipeline_id, 'version': state.version},
                retry_policy=retry_policy,
            )
            yield ctx.call_activity(
                names['publish_activation_event'],
                input={'activation_record': activation_raw},
                retry_policy=retry_policy,
            )

        final_raw = yield ctx.call_activity(
            names['update_status'],
            input={
                'pipeline_id': state.pipeline_id,
                'version': state.version,
                'stage': (
                    PipelineStage.COMPLETED.value
                    if validation.valid
                    else PipelineStage.FAILED.value
                ),
                'validation_succeeded': validation.valid,
                'activation_succeeded': activation_succeeded,
                'active_version': active_version,
                'completed_at': ctx.current_utc_datetime.isoformat(),
            },
            retry_policy=retry_policy,
        )
        return final_raw

    def _orchestrate_activation(self, ctx: DaprWorkflowContext, wf_input: dict):
        payload = from_wire(wf_input, _ActivationState)
        retry_policy = _retry_policy_from(self._config)
        names = self._activity_names

        validation_raw = yield ctx.call_activity(
            names['validate_version'],
            input={'pipeline_id': payload.pipeline_id, 'version': payload.version},
            retry_policy=retry_policy,
        )
        validation = from_wire(validation_raw, ValidationResult)
        if not validation.valid:
            raise VersionValidationError(
                f'Version {payload.version!r} failed validation: {validation.details}'
            )

        activation_raw = yield ctx.call_activity(
            names['activate_version'],
            input={'pipeline_id': payload.pipeline_id, 'version': payload.version},
            retry_policy=retry_policy,
        )
        yield ctx.call_activity(
            names['register_foundry_iq_knowledge_source'],
            input={'pipeline_id': payload.pipeline_id, 'version': payload.version},
            retry_policy=retry_policy,
        )
        yield ctx.call_activity(
            names['publish_activation_event'],
            input={'activation_record': activation_raw},
            retry_policy=retry_policy,
        )
        return activation_raw

    # -- activities (all I/O; no determinism constraints) -------------------

    def _activity_discover_and_manifest(self, ctx: WorkflowActivityContext, raw: dict) -> dict:
        pipeline_id, version = raw['pipeline_id'], raw['version']
        documents = [
            DocumentWorkItem.from_source_document(doc)
            for doc in self._source.list_documents(raw.get('prefix'))
        ]
        summary = self._state.write_manifest(
            pipeline_id=pipeline_id,
            version=version,
            documents=documents,
            page_size=raw['page_size'],
            manifest_hash=compute_manifest_hash(d.document_id for d in documents),
            created_at=_utcnow_iso(),
        )
        return to_wire(summary)

    def _activity_get_manifest_batch(self, ctx: WorkflowActivityContext, raw: dict) -> dict:
        items = self._state.read_manifest_page(
            pipeline_id=raw['pipeline_id'], version=raw['version'], page_index=raw['page_index']
        )
        return {'items': [dataclasses.asdict(item) for item in items]}

    def _activity_process_document(self, ctx: WorkflowActivityContext, raw: dict) -> dict:
        work_item = DocumentWorkItem(**raw['work_item'])
        pipeline_id, version = raw['pipeline_id'], raw['version']
        attempts = self._state.increment_attempt_count(
            pipeline_id=pipeline_id, version=version, document_id=work_item.document_id
        )
        self._failure_injector.maybe_fail_before_start(work_item.document_id, attempts)

        try:
            outcome = self._process_one_document(
                work_item=work_item,
                pipeline_id=pipeline_id,
                version=version,
                pipeline_fingerprint=raw['pipeline_fingerprint'],
                document_ordinal=raw['document_ordinal'],
                workflow_instance_id=ctx.workflow_id,
                attempts=attempts,
            )
        except RetryableError:
            raise  # let the outer RetryPolicy back off and retry the whole activity
        except NonRetryableError as exc:
            outcome = DocumentOutcome(
                document_id=work_item.document_id,
                status=DocumentOutcomeStatus.FAILED.value,
                attempts=attempts,
                error_type=type(exc).__name__,
                error_message=str(exc)[:500],
                retryable=False,
            )
        return to_wire(outcome)

    def _process_one_document(
        self,
        *,
        work_item: DocumentWorkItem,
        pipeline_id: str,
        version: str,
        pipeline_fingerprint: str,
        document_ordinal: int,
        workflow_instance_id: str,
        attempts: int,
    ) -> DocumentOutcome:
        prior = self._state.read_completion(
            pipeline_id=pipeline_id, version=version, document_id=work_item.document_id
        )

        current_metadata: SourceMetadata = self._source.get_metadata(work_item.document_id)
        if (
            work_item.source_etag
            and current_metadata.etag
            and current_metadata.etag != work_item.source_etag
        ):
            raise DocumentChangedError(
                f'{work_item.document_id} changed since discovery (etag '
                f'{work_item.source_etag!r} -> {current_metadata.etag!r}); it will be picked up '
                'on a later run rather than indexed under stale manifest metadata.'
            )

        content = self._source.get_document(work_item.document_id)
        content_hash = compute_content_hash(content)

        if (
            prior is not None
            and prior.source_content_hash == content_hash
            and prior.pipeline_fingerprint == pipeline_fingerprint
            and prior.status == DocumentOutcomeStatus.COMPLETED.value
        ):
            return DocumentOutcome(
                document_id=work_item.document_id,
                status=DocumentOutcomeStatus.SKIPPED.value,
                chunk_count=prior.chunk_count,
                reused_chunk_count=prior.chunk_count,
                bytes_processed=0,
                attempts=attempts,
            )

        source_document = SourceDocument(
            document_id=work_item.document_id,
            provider=SourceProvider(work_item.provider),
            uri=work_item.uri,
            name=work_item.name,
            metadata=current_metadata,
        )
        parsed_documents = self._parser.parse(content, source_document)
        chunks = [chunk for doc in parsed_documents for chunk in self._splitter.split(doc)]

        parser_config_hash = self._parser.config_fingerprint()
        splitter_config_hash = self._splitter.config_fingerprint()
        embedding_model = self._embedder.embedding_model
        chunk_content_hashes = [compute_content_hash(c.content.encode('utf-8')) for c in chunks]
        chunk_ids = [
            compute_chunk_id(
                source_document_id=work_item.document_id,
                source_content_hash=content_hash,
                parser_config_hash=parser_config_hash,
                splitter_config_hash=splitter_config_hash,
                chunk_ordinal=chunk.chunk_ordinal,
                chunk_content_hash=chunk_content_hashes[i],
                embedding_model=embedding_model,
            )
            for i, chunk in enumerate(chunks)
        ]

        progress = self._state.read_embed_progress(
            pipeline_id=pipeline_id, version=version, document_id=work_item.document_id
        )
        if (
            progress is None
            or progress.source_content_hash != content_hash
            or progress.pipeline_fingerprint != pipeline_fingerprint
        ):
            progress = EmbedProgressRecord(
                document_id=work_item.document_id,
                source_content_hash=content_hash,
                pipeline_fingerprint=pipeline_fingerprint,
                total_batches=(
                    math.ceil(len(chunks) / self._config.embedding_batch_size) if chunks else 0
                ),
            )

        embedded_count = 0
        reused_count = 0
        batch_size = self._config.embedding_batch_size
        for batch_index, batch_start in enumerate(range(0, len(chunks), batch_size)):
            batch_chunks = chunks[batch_start : batch_start + batch_size]

            if batch_index in progress.completed_batch_indices:
                reused_count += len(batch_chunks)
                continue

            self._failure_injector.maybe_fail_during_embedding(work_item.document_id, batch_index)

            batch_chunk_ids = chunk_ids[batch_start : batch_start + batch_size]
            batch_hashes = chunk_content_hashes[batch_start : batch_start + batch_size]
            embedding_result = self._embedder.embed_batch([c.content for c in batch_chunks])
            embedded_count += len(batch_chunks)

            ingested_at = _utcnow_iso()
            records = []
            for local_index, chunk in enumerate(batch_chunks):
                provenance = ProvenanceRecord(
                    chunk_id=batch_chunk_ids[local_index],
                    pipeline_id=pipeline_id,
                    workflow_instance_id=workflow_instance_id,
                    source_provider=work_item.provider,
                    source_document_id=work_item.document_id,
                    source_uri=work_item.uri,
                    source_name=work_item.name,
                    source_content_hash=content_hash,
                    source_etag=current_metadata.etag,
                    source_version_id=current_metadata.version_id,
                    source_content_type=current_metadata.content_type,
                    document_ordinal=document_ordinal,
                    chunk_ordinal=chunk.chunk_ordinal,
                    chunk_content_hash=batch_hashes[local_index],
                    parser_type=self._parser.parser_type,
                    parser_config_hash=parser_config_hash,
                    splitter_type=self._splitter.splitter_type,
                    splitter_config_hash=splitter_config_hash,
                    embedding_provider=type(self._embedder).__name__,
                    embedding_model=embedding_model,
                    target_index=self._vector_store.target_index_name,
                    target_version=version,
                    ingested_at=ingested_at,
                    activity_attempt=attempts,
                    # Duck-typed: only embedders with a separate deployment concept
                    # (e.g. AzureOpenAIEmbedder) expose `.deployment`; None otherwise.
                    embedding_deployment=getattr(self._embedder, 'deployment', None),
                )
                records.append(
                    VectorRecord(
                        chunk_id=batch_chunk_ids[local_index],
                        document_id=work_item.document_id,
                        content=chunk.content,
                        embedding=embedding_result.embeddings[local_index],
                        metadata={**chunk.metadata, **provenance.to_dict()},
                    )
                )
            self._vector_store.upsert(records, version)

            self._failure_injector.maybe_fail_after_embedding_before_completion(
                work_item.document_id, batch_index
            )

            # Progress is only recorded *after* the upsert above durably lands --
            # a crash between them simply re-embeds and re-upserts this one batch
            # on the next attempt, which is safe because upserts are idempotent.
            progress = dataclasses.replace(
                progress, completed_batch_indices=[*progress.completed_batch_indices, batch_index]
            )
            self._state.write_embed_progress(
                pipeline_id=pipeline_id, version=version, record=progress
            )

        self._state.write_completion(
            pipeline_id=pipeline_id,
            version=version,
            record=CompletionRecord(
                document_id=work_item.document_id,
                source_content_hash=content_hash,
                pipeline_fingerprint=pipeline_fingerprint,
                chunk_count=len(chunks),
                embedded_chunk_count=embedded_count,
                completed_at=_utcnow_iso(),
            ),
        )
        return DocumentOutcome(
            document_id=work_item.document_id,
            status=DocumentOutcomeStatus.COMPLETED.value,
            chunk_count=len(chunks),
            embedded_chunk_count=embedded_count,
            reused_chunk_count=reused_count,
            bytes_processed=len(content),
            attempts=attempts,
        )

    def _activity_validate_version(self, ctx: WorkflowActivityContext, raw: dict) -> dict:
        pipeline_id, version = raw['pipeline_id'], raw['version']
        expected_documents = raw.get('expected_documents')
        manifest_meta = (
            self._state.read_manifest_meta(pipeline_id=pipeline_id, version=version) or {}
        )
        if expected_documents is None:
            expected_documents = manifest_meta.get('total_documents', 0)

        store_result = self._vector_store.validate_version(version)

        page_count = manifest_meta.get('page_count', 0)
        completed_documents = 0
        expected_chunk_count = 0
        for page_index in range(page_count):
            page = self._state.read_manifest_page(
                pipeline_id=pipeline_id, version=version, page_index=page_index
            )
            for item in page:
                record = self._state.read_completion(
                    pipeline_id=pipeline_id, version=version, document_id=item.document_id
                )
                if record is not None and record.status == DocumentOutcomeStatus.COMPLETED.value:
                    completed_documents += 1
                    expected_chunk_count += record.chunk_count

        # A version with zero expected documents is treated as invalid rather than
        # trivially valid: it's far more likely to be a misconfigured prefix/source
        # than an intentional empty index, and activating one would silently
        # blank out query results for that pipeline.
        valid = (
            expected_documents > 0
            and completed_documents == expected_documents
            and store_result.actual_chunk_count >= expected_chunk_count
        )
        result = dataclasses.replace(
            store_result,
            valid=valid,
            expected_document_count=expected_documents,
            expected_chunk_count=expected_chunk_count,
            details=(
                f'{completed_documents}/{expected_documents} document(s) completed; '
                f'{store_result.actual_chunk_count} chunk(s) in store (expected '
                f'{expected_chunk_count}).'
            ),
        )
        return to_wire(result)

    def _activity_activate_version(self, ctx: WorkflowActivityContext, raw: dict) -> dict:
        pipeline_id, version = raw['pipeline_id'], raw['version']
        manifest_hash = raw.get('manifest_hash')
        if manifest_hash is None:
            meta = self._state.read_manifest_meta(pipeline_id=pipeline_id, version=version) or {}
            manifest_hash = meta.get('manifest_hash', '')
        workflow_instance_id = raw.get('workflow_instance_id') or ctx.workflow_id

        current, etag = self._state.read_activation(pipeline_id)
        if (
            current is not None
            and current.active_version == version
            and current.manifest_hash == manifest_hash
        ):
            return to_wire(current)  # already active under this exact manifest: idempotent no-op

        previous_version = current.active_version if current is not None else None
        # Store-native activation (e.g. AzureAISearchVectorStore's alias switch) runs
        # before the Dapr-state write and is a no-op for stores without one (see
        # VectorIndex.activate_version's default). This ordering makes a retry after a
        # partial failure safe: re-running finds the store's own state already correct
        # and just completes the Dapr-state write, rather than switching twice.
        self._vector_store.activate_version(version, previous_version=previous_version)

        record = ActivationRecord(
            pipeline_id=pipeline_id,
            active_version=version,
            previous_version=previous_version,
            manifest_hash=manifest_hash,
            activated_at=_utcnow_iso(),
            workflow_instance_id=workflow_instance_id,
        )
        self._state.write_activation(record, etag=etag)
        return to_wire(record)

    def _activity_publish_activation_event(self, ctx: WorkflowActivityContext, raw: dict) -> dict:
        if not self._pubsub_name:
            return {'published': False}
        try:
            self._dapr_client.publish_event(
                pubsub_name=self._pubsub_name,
                topic_name=self._pubsub_topic,
                data=json.dumps(raw['activation_record']),
                data_content_type='application/json',
            )
            return {'published': True}
        except Exception as exc:
            # Best-effort: a notification failure must not fail an otherwise
            # successful activation.
            logger.warning('Failed to publish %s event: %s', self._pubsub_topic, exc)
            return {'published': False}

    def _activity_register_foundry_iq_knowledge_source(
        self, ctx: WorkflowActivityContext, raw: dict
    ) -> dict:
        """Opt-in: see `foundry_iq_knowledge_source` on `__init__` and `docs/rag/foundry-iq.md`.

        Only ever called after `activate_version` has already succeeded for
        `raw['version']` (see `_orchestrate_ingestion`/`_orchestrate_activation`), so this
        never registers a knowledge source for a version that hasn't passed this
        pipeline's own validation gate. Best-effort, like `_activity_publish_activation_
        event`: a registration failure is logged, not raised, so it never fails an
        otherwise-successful activation -- Foundry IQ registration is a convenience on
        top of activation, not a precondition for it.
        """
        config = self._foundry_iq_knowledge_source
        if config is None:
            return {'registered': False}
        try:
            # Not every VectorIndex supports this (only AzureAISearchVectorStore currently
            # does) -- __init__ already validated vector_store has the method whenever
            # foundry_iq_knowledge_source is set, so this dynamic call is safe at runtime;
            # getattr sidesteps a static attribute check against the base VectorIndex ABC.
            register = getattr(self._vector_store, 'register_foundry_iq_knowledge_source')
            register(
                raw['version'],
                name=config.name,
                description=config.description,
                source_data_fields=list(config.source_data_fields),
                search_fields=list(config.search_fields),
            )
            return {'registered': True}
        except Exception as exc:
            logger.warning(
                'Failed to register Foundry IQ knowledge source %s: %s', config.name, exc
            )
            return {'registered': False}

    def _activity_update_status(self, ctx: WorkflowActivityContext, raw: dict) -> dict:
        pipeline_id, version = raw['pipeline_id'], raw['version']
        now = _utcnow_iso()
        this_run_instance_id = raw.get('workflow_instance_id') or ctx.workflow_id

        current = self._state.read_status(pipeline_id=pipeline_id, version=version)
        if current is None or current.workflow_instance_id != this_run_instance_id:
            # Either the very first status write for this (pipeline_id, version), or a
            # *different* workflow instance re-running a version whose last attempt already
            # reached a terminal status (DurableRAGPipeline.start() explicitly supports this --
            # see its docstring). Either way, counters must restart from zero here: carrying
            # forward a prior instance's counts would silently double-count documents that both
            # runs discover independently. When the same stable instance ID is reused (the
            # common resume-after-failure case), this is a no-op: it already matches `current`.
            current = PipelineStatus(
                pipeline_id=pipeline_id,
                requested_version=version,
                workflow_instance_id=this_run_instance_id,
                started_at=now,
            )

        total_documents = raw.get('total_documents', current.total_documents)
        outcomes = [DocumentOutcome(**item) for item in raw.get('outcomes', [])]

        completed, skipped, failed = (
            current.completed_documents,
            current.skipped_documents,
            current.failed_documents,
        )
        total_chunks, embedded_chunks, reused_chunks = (
            current.total_chunks,
            current.embedded_chunks,
            current.reused_chunks,
        )
        embedding_requests = current.embedding_requests
        bytes_processed = current.bytes_processed
        retry_count = current.retry_count
        retry_by_activity = dict(current.retry_count_by_activity)
        failures = list(current.failures)

        for outcome in outcomes:
            if outcome.status == DocumentOutcomeStatus.COMPLETED.value:
                completed += 1
            elif outcome.status == DocumentOutcomeStatus.SKIPPED.value:
                skipped += 1
            else:
                failed += 1
                failures.append(
                    DocumentFailure(
                        document_id=outcome.document_id,
                        error_type=outcome.error_type or 'Unknown',
                        error_message=outcome.error_message or '',
                        retryable=bool(outcome.retryable),
                    )
                )
            total_chunks += outcome.chunk_count
            embedded_chunks += outcome.embedded_chunk_count
            reused_chunks += outcome.reused_chunk_count
            bytes_processed += outcome.bytes_processed
            if outcome.embedded_chunk_count:
                embedding_requests += 1  # one embed_batch call per non-empty embedded batch
            if outcome.attempts > 1:
                retry_count += outcome.attempts - 1
                retry_by_activity['process_document'] = (
                    retry_by_activity.get('process_document', 0) + outcome.attempts - 1
                )

        pending = max(total_documents - (completed + skipped + failed), 0)
        completed_at = raw.get('completed_at', current.completed_at)
        duration_seconds = current.duration_seconds
        if completed_at and current.started_at:
            duration_seconds = (
                _parse_iso(completed_at) - _parse_iso(current.started_at)
            ).total_seconds()

        new_status = dataclasses.replace(
            current,
            stage=raw.get('stage', current.stage),
            total_documents=total_documents,
            pending_documents=pending,
            running_documents=0,
            completed_documents=completed,
            skipped_documents=skipped,
            failed_documents=failed,
            total_chunks=total_chunks,
            embedded_chunks=embedded_chunks,
            reused_chunks=reused_chunks,
            embedding_requests=embedding_requests,
            avoided_embedding_units=reused_chunks,
            retry_count=retry_count,
            retry_count_by_activity=retry_by_activity,
            bytes_processed=bytes_processed,
            active_version=raw.get('active_version', current.active_version),
            validation_succeeded=raw.get('validation_succeeded', current.validation_succeeded),
            activation_succeeded=raw.get('activation_succeeded', current.activation_succeeded),
            updated_at=now,
            completed_at=completed_at,
            duration_seconds=duration_seconds,
            failures=tuple(failures),
        )
        self._state.write_status(new_status)
        return new_status.to_dict()
