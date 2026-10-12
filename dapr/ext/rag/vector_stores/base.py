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

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Iterable, Optional, Sequence

from dapr.ext.rag.models import QueryMatch, UpsertResult, ValidationResult, VectorRecord


class VectorIndex(ABC):
    """A versioned vector store: every write and read is scoped to a version.

    Versions let a new ingestion run build a complete index alongside the
    currently-active one without ever writing into it -- see `state.py`'s
    `PipelineStateStore.write_activation` for how a version is promoted to
    active only after `validate_version` passes. Implementations perform I/O
    and must only ever be called from within a workflow activity, never from
    the orchestrator.
    """

    @property
    @abstractmethod
    def target_index_name(self) -> str:
        """The collection/index name this store writes to, for provenance."""

    @property
    @abstractmethod
    def store_type(self) -> str:
        """A short, stable name identifying this store (e.g. 'pgvector')."""

    @abstractmethod
    def upsert(self, records: Iterable[VectorRecord], version: str) -> UpsertResult:
        """Writes records into `version`, keyed by each record's `chunk_id`.

        Must be idempotent: upserting the same `chunk_id` twice (e.g. after
        an activity retry) overwrites rather than duplicates.

        Raises:
            TransientVectorStoreError: The write failed transiently.
            VectorStoreError: The write failed non-transiently.
        """

    @abstractmethod
    def delete_document(self, document_id: str, version: str) -> None:
        """Removes every chunk belonging to `document_id` within `version`."""

    @abstractmethod
    def validate_version(self, version: str) -> ValidationResult:
        """Reports what this store actually holds for `version`.

        Implementations can only observe their own contents, so
        `expected_document_count` / `expected_chunk_count` are left `None`
        here; `pipeline.py`'s validation activity fills those in from the
        manifest before using the result to gate activation.
        """

    @abstractmethod
    def query(
        self,
        embedding: Sequence[float],
        version: str,
        *,
        top_k: int = 5,
        metadata_filter: Optional[dict[str, Any]] = None,
        query_text: Optional[str] = None,
    ) -> list[QueryMatch]:
        """Runs a similarity search scoped to one version.

        Not part of the spec's original `VectorIndex` sketch (which covers
        only writes and validation), but added here rather than in
        provider-specific code: retrieval is an explicit requirement (the
        sample CLI's "query" command, and `retrieval.py`'s active-version
        helper), and this is the one place that can serve it without
        provider-specific branching leaking into either of those callers.

        Args:
            embedding: The query embedding, from the same model used to
                embed the indexed chunks.
            version: The version to search within.
            top_k: Maximum number of matches to return.
            metadata_filter: An optional, store-specific metadata filter
                (e.g. `{'document_id': {'$eq': '...'}}` for Pinecone).
            query_text: The original query text, for stores that combine
                keyword/full-text search with vector search (e.g.
                `AzureAISearchVectorStore`'s hybrid mode). Purely
                vector-based stores accept and ignore it.

        Returns:
            Up to `top_k` `QueryMatch`es, ordered by descending score.
        """

    def activate_version(self, version: str, *, previous_version: Optional[str]) -> None:
        """Performs any store-native activation step, in addition to the Dapr-state pointer.

        The default implementation is a no-op: most stores (pgvector,
        Pinecone) have no separate "physical" activation step -- the Dapr
        state `ActivationRecord` (see `state.py`) is the only routing
        mechanism, since `version` there is just a column/namespace value
        within one always-queryable physical index/table.

        A store built around one physical index *per version* (e.g.
        `AzureAISearchVectorStore`, which creates `{base}-{version}`)
        overrides this to atomically point a stable alias at the new
        version's index -- see that class for the retry-safe read-check-
        write-poll sequence this method is expected to perform. Called from
        `pipeline.py`'s `_activity_activate_version`, inside a workflow
        activity, before the Dapr-state write -- so a retry after a partial
        failure re-checks this store's own state first and finds it already
        correct (no-op) rather than double-switching.

        Must be idempotent and safe to call repeatedly with the same
        `version` (e.g. on activity retry).

        Raises:
            TransientVectorStoreError: The activation step failed transiently.
            VectorStoreError: The activation step failed non-transiently.
        """

    def close(self) -> None:
        """Releases any held resources (connections, sessions). Optional to override."""
