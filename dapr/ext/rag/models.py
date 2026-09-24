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

# Typed data models shared across dapr.ext.rag adapters and the pipeline.
#
# This module has no dependency beyond the standard library so every adapter
# (including ones guarding an optional third-party import) and every test can
# import it unconditionally.
#
# Two shapes of model live here:
#   - Flat models (all fields are JSON primitives, or lists/dicts of them):
#     these cross the workflow activity boundary via `_wire.to_wire` /
#     `_wire.from_wire`, e.g. `DocumentWorkItem`, `DocumentOutcome`.
#   - Richer, possibly-nested models used only within a single activity's
#     body or by adapters directly, e.g. `SourceDocument`, `Chunk`.

from __future__ import annotations

import dataclasses
import enum
from dataclasses import dataclass, field
from typing import Any, Mapping, Optional, Sequence


class SourceProvider(str, enum.Enum):
    """Identifies which `DocumentSource` implementation produced a document."""

    S3 = 's3'
    AZURE_BLOB = 'azure-blob'


@dataclass(frozen=True, slots=True)
class SourceMetadata:
    """Point-in-time metadata describing a document at its source.

    All fields are best-effort: not every source or object may expose all of
    them (e.g. a source that doesn't version objects has no `version_id`).
    """

    etag: Optional[str] = None
    version_id: Optional[str] = None
    last_modified: Optional[str] = None  # ISO-8601, set inside an activity
    content_length: Optional[int] = None
    content_type: Optional[str] = None


@dataclass(frozen=True, slots=True)
class SourceDocument:
    """A document discovered at a `DocumentSource`, identified stably across runs."""

    document_id: str
    provider: SourceProvider
    uri: str
    name: str
    metadata: SourceMetadata = field(default_factory=SourceMetadata)


@dataclass(frozen=True, slots=True)
class DocumentWorkItem:
    """The flat, wire-safe projection of a `SourceDocument`.

    This is what actually crosses the workflow activity boundary (as manifest
    batch elements, and as `process_document`'s input) -- see `_wire.py` for
    why nested dataclass fields like `SourceDocument.metadata` don't survive
    that trip.
    """

    document_id: str
    provider: str
    uri: str
    name: str
    source_etag: Optional[str] = None
    source_version_id: Optional[str] = None
    source_content_length: Optional[int] = None

    @classmethod
    def from_source_document(cls, doc: SourceDocument) -> 'DocumentWorkItem':
        """Flattens a `SourceDocument` for the manifest and activity input."""
        return cls(
            document_id=doc.document_id,
            provider=doc.provider.value,
            uri=doc.uri,
            name=doc.name,
            source_etag=doc.metadata.etag,
            source_version_id=doc.metadata.version_id,
            source_content_length=doc.metadata.content_length,
        )


@dataclass(frozen=True, slots=True)
class SourceChangeEvent:
    """A provider-neutral "something changed at this document" notification.

    Normalizes an S3 Event Notification or an Azure Event Grid blob event
    (see `triggers.py`) into one shape a trigger handler can act on without
    branching on provider. `event_id` is the provider's own event/message ID
    (e.g. Event Grid's `id`, or an S3 notification has none, so callers
    derive a stable one -- see `triggers.py`) and is the idempotency key an
    `EventDeduplicator` checks before starting or re-triggering ingestion.

    Deliberately a flat dataclass rather than the pydantic `BaseModel` a
    provider-neutral event sketch might suggest: this repo's own typed-model
    convention is dataclasses (see `_wire.py`'s module comment), and
    `provider` reuses this package's existing `SourceProvider` values
    ('s3' / 'azure-blob') rather than introducing a second, differently
    spelled vocabulary.
    """

    provider: str  # SourceProvider value
    event_type: str  # 'created' | 'updated' | 'deleted'
    source_document_id: str
    uri: str
    etag: Optional[str]
    version_id: Optional[str]
    occurred_at: Optional[str]  # ISO-8601 when the provider reports one
    event_id: str

    def to_dict(self) -> dict[str, Any]:
        return dataclasses.asdict(self)

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> 'SourceChangeEvent':
        return cls(**dict(data))


@dataclass(frozen=True, slots=True)
class Document:
    """Parsed content plus metadata for one logical unit (e.g. a PDF page).

    Mirrors LangChain's `Document` shape without requiring LangChain to be
    installed -- see `parsing/langchain.py` for lossless conversion.
    """

    page_content: str
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class Chunk:
    """One splitter-produced unit of text, ordered within its parsed document."""

    chunk_ordinal: int
    content: str
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class VectorRecord:
    """A single chunk ready to be written to a `VectorIndex`."""

    chunk_id: str
    document_id: str
    content: str
    embedding: Sequence[float]
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class EmbeddingBatchResult:
    """The result of embedding one batch of chunk texts."""

    embeddings: list[Sequence[float]]
    total_tokens: Optional[int] = None


@dataclass(frozen=True, slots=True)
class QueryMatch:
    """One similarity-search result from `VectorIndex.query()`."""

    chunk_id: str
    document_id: str
    content: str
    score: float
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class UpsertResult:
    """Outcome of writing a batch of `VectorRecord`s to a `VectorIndex`."""

    upserted_count: int
    version: str


@dataclass(frozen=True, slots=True)
class ValidationResult:
    """Outcome of comparing a built index version against its manifest.

    A `VectorIndex.validate_version()` implementation only knows what's
    actually stored, and not every store can cheaply report a distinct
    document count (e.g. Pinecone's stats API reports vector counts per
    namespace but not distinct metadata-field counts) -- so only
    `actual_chunk_count` is guaranteed. `pipeline.py`'s validation activity
    fills in the `expected_*` fields from the manifest/completion records
    (via `dataclasses.replace`) and recomputes `valid` before using the
    result to gate activation.
    """

    valid: bool
    version: str
    actual_chunk_count: int
    expected_document_count: Optional[int] = None
    expected_chunk_count: Optional[int] = None
    actual_document_count: Optional[int] = None
    details: str = ''


@dataclass(frozen=True, slots=True)
class ActivationRecord:
    """The active-version pointer for one pipeline, persisted in Dapr state."""

    pipeline_id: str
    active_version: str
    previous_version: Optional[str]
    manifest_hash: str
    activated_at: str  # ISO-8601, set inside an activity
    workflow_instance_id: str

    def to_dict(self) -> dict[str, Any]:
        return dataclasses.asdict(self)

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> 'ActivationRecord':
        return cls(**dict(data))


@dataclass(frozen=True, slots=True)
class ProvenanceRecord:
    """Everything needed to answer "where did this chunk's vector come from?"

    Deliberately flat and JSON-primitive-only so it can be signed or
    externally attested later without redesigning the stored shape.
    """

    chunk_id: str
    pipeline_id: str
    workflow_instance_id: str
    source_provider: str
    source_document_id: str
    source_uri: str
    source_name: str
    source_content_hash: str
    source_etag: Optional[str]
    source_version_id: Optional[str]
    source_content_type: Optional[str]
    document_ordinal: int
    chunk_ordinal: int
    chunk_content_hash: str
    parser_type: str
    parser_config_hash: str
    splitter_type: str
    splitter_config_hash: str
    embedding_provider: str
    embedding_model: str
    target_index: str
    target_version: str
    ingested_at: str  # ISO-8601, set inside an activity
    activity_attempt: Optional[int] = None
    # The deployment name is distinct from the underlying model (Azure OpenAI:
    # a customer-chosen deployment alias fronting a specific model version).
    # None for embedders with no separate deployment concept (e.g. OpenAIEmbedder).
    embedding_deployment: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        return dataclasses.asdict(self)

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> 'ProvenanceRecord':
        return cls(**dict(data))


class DocumentOutcomeStatus(str, enum.Enum):
    """The result of processing one document within an ingestion run."""

    COMPLETED = 'completed'
    SKIPPED = 'skipped'
    FAILED = 'failed'


@dataclass(frozen=True, slots=True)
class DocumentOutcome:
    """The flat result of the `process_document` activity for one document."""

    document_id: str
    status: str  # DocumentOutcomeStatus value
    chunk_count: int = 0
    embedded_chunk_count: int = 0
    reused_chunk_count: int = 0
    bytes_processed: int = 0
    attempts: int = 1
    error_type: Optional[str] = None
    error_message: Optional[str] = None
    retryable: Optional[bool] = None


@dataclass(frozen=True, slots=True)
class DocumentFailure:
    """A compact, status-report-friendly view of a failed `DocumentOutcome`."""

    document_id: str
    error_type: str
    error_message: str
    retryable: bool


@dataclass(frozen=True, slots=True)
class ManifestSummary:
    """The flat result of the `discover_and_manifest` activity.

    The full list of `DocumentWorkItem`s is persisted to Dapr state in pages
    (see `state.py`) rather than returned here, so it never enters workflow
    history.
    """

    version: str
    total_documents: int
    manifest_hash: str
    page_size: int
    created_at: str  # ISO-8601, set inside an activity


@dataclass(frozen=True, slots=True)
class CompletionRecord:
    """Persisted proof that a document was fully indexed under a given fingerprint.

    Read at the top of `process_document` to decide whether to skip a
    document entirely; written only after its vectors are durably upserted.
    """

    document_id: str
    source_content_hash: str
    pipeline_fingerprint: str
    chunk_count: int
    embedded_chunk_count: int
    completed_at: str  # ISO-8601, set inside an activity
    status: str = DocumentOutcomeStatus.COMPLETED.value

    def to_dict(self) -> dict[str, Any]:
        return dataclasses.asdict(self)

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> 'CompletionRecord':
        return cls(**dict(data))


@dataclass(frozen=True, slots=True)
class EmbedProgressRecord:
    """Tracks which embedding batches of one document have been durably upserted.

    Lets `process_document` resume mid-document after a crash without
    re-embedding batches that already made it to the vector store -- see
    `dapr/ext/rag/AGENTS.md` for the checkpoint-after-durable-write ordering
    this depends on.
    """

    document_id: str
    source_content_hash: str
    pipeline_fingerprint: str
    total_batches: int
    completed_batch_indices: list[int] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return dataclasses.asdict(self)

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> 'EmbedProgressRecord':
        payload = dict(data)
        payload['completed_batch_indices'] = list(payload.get('completed_batch_indices', []))
        return cls(**payload)


class PipelineStage(str, enum.Enum):
    """The ingestion workflow's current logical stage, for status reporting."""

    DISCOVERING = 'discovering'
    PROCESSING_DOCUMENTS = 'processing_documents'
    VALIDATING = 'validating'
    ACTIVATING = 'activating'
    COMPLETED = 'completed'
    FAILED = 'failed'


@dataclass(frozen=True, slots=True)
class PipelineConfig:
    """User-tunable knobs for a `DurableRAGPipeline` run.

    All fields are plain primitives (rather than e.g. `timedelta`) so this
    config can be embedded verbatim in workflow input and hashed as part of
    the pipeline fingerprint (see `fingerprints.py`).
    """

    max_concurrent_documents: int = 10
    embedding_batch_size: int = 64
    max_activity_attempts: int = 5
    fail_fast: bool = False
    first_retry_interval_seconds: float = 5.0
    backoff_coefficient: float = 2.0
    max_retry_interval_seconds: float = 300.0
    manifest_page_size: Optional[int] = None

    def __post_init__(self) -> None:
        if self.max_concurrent_documents < 1:
            raise ValueError('max_concurrent_documents must be >= 1')
        if self.embedding_batch_size < 1:
            raise ValueError('embedding_batch_size must be >= 1')
        if self.max_activity_attempts < 1:
            raise ValueError('max_activity_attempts must be >= 1')

    @property
    def effective_manifest_page_size(self) -> int:
        """The manifest page size, defaulting to `max_concurrent_documents`.

        Manifest pages double as fan-out batches, so sizing them the same as
        `max_concurrent_documents` means one page read yields exactly one
        bounded batch of concurrent `process_document` activity calls.
        """
        return self.manifest_page_size or self.max_concurrent_documents

    def to_dict(self) -> dict[str, Any]:
        return dataclasses.asdict(self)

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> 'PipelineConfig':
        return cls(**dict(data))


@dataclass(frozen=True, slots=True)
class FoundryIQKnowledgeSourceConfig:
    """Opt-in: registers this pipeline's activated Azure AI Search index as a Foundry IQ
    search-index knowledge source. See `docs/rag/foundry-iq.md` for the full rationale --
    this is off by default, and only meaningful with `AzureAISearchVectorStore`.

    A constructor-level `DurableRAGPipeline` setting (like `pubsub_name`/`pubsub_topic`),
    not a per-run one: every worker process must construct the pipeline with the same
    value for the registration activity to behave consistently across restarts.
    """

    name: str
    """The Foundry IQ knowledge source's name."""

    description: Optional[str] = None
    source_data_fields: tuple[str, ...] = ()
    """Index field names to return as source data for a matched chunk."""
    search_fields: tuple[str, ...] = ()
    """Index field names Foundry IQ's own retrieval searches over. Defaults (empty) to
    Azure AI Search's own default of all searchable fields."""


@dataclass(frozen=True, slots=True)
class PipelineStatus:
    """A point-in-time snapshot of an ingestion run, persisted in Dapr state.

    This is both the record `pipeline.get_status(...)` reads and the shape of
    the ingestion workflow's own final return value.
    """

    pipeline_id: str
    requested_version: str
    workflow_instance_id: str
    stage: str = PipelineStage.DISCOVERING.value
    active_version: Optional[str] = None
    total_documents: int = 0
    pending_documents: int = 0
    running_documents: int = 0
    completed_documents: int = 0
    skipped_documents: int = 0
    failed_documents: int = 0
    total_chunks: int = 0
    embedded_chunks: int = 0
    reused_chunks: int = 0
    embedding_requests: int = 0
    avoided_embedding_units: int = 0
    retry_count: int = 0
    retry_count_by_activity: dict[str, int] = field(default_factory=dict)
    bytes_processed: int = 0
    validation_succeeded: Optional[bool] = None
    activation_succeeded: Optional[bool] = None
    started_at: Optional[str] = None
    updated_at: Optional[str] = None
    completed_at: Optional[str] = None
    duration_seconds: Optional[float] = None
    failures: tuple[DocumentFailure, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return dataclasses.asdict(self)

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> 'PipelineStatus':
        payload = dict(data)
        raw_failures = payload.pop('failures', None) or ()
        failures = tuple(
            f if isinstance(f, DocumentFailure) else DocumentFailure(**f) for f in raw_failures
        )
        return cls(**payload, failures=failures)


@dataclass(frozen=True, slots=True)
class Citation:
    """One retrieved chunk cited in a generated answer."""

    title: str
    source_uri: str
    chunk_id: str
    score: float


@dataclass(frozen=True, slots=True)
class AnswerResult:
    """A grounded answer plus the chunks it was generated from.

    `sufficient_evidence=False` means retrieval didn't surface enough
    relevant context; `answer` is then a refusal/insufficient-evidence
    message rather than a best-effort guess.
    """

    answer: str
    citations: tuple[Citation, ...]
    index_version: str
    sufficient_evidence: bool = True
    workflow_instance_id: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        return dataclasses.asdict(self)
