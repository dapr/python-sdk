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

from typing import Any, Iterable, Iterator, Optional, TypeVar

from dapr.ext.rag.errors import (
    OptionalDependencyError,
    RagError,
    TransientVectorStoreError,
    VectorStoreError,
)
from dapr.ext.rag.models import QueryMatch, UpsertResult, ValidationResult, VectorRecord
from dapr.ext.rag.vector_stores.base import VectorIndex

# See dapr/ext/rag/AGENTS.md for why the optional-dependency guard lives here,
# per adapter module, rather than once in dapr/ext/rag/__init__.py.
try:
    from pinecone import Pinecone
except ImportError:  # pragma: no cover - exercised only without pinecone installed
    Pinecone = None  # type: ignore[assignment]

_TRANSIENT_EXCEPTION_NAMES = frozenset(
    {
        'ServiceException',
        'UnauthorizedException',
        'PineconeApiException',
        'MaxRetryError',
        'TimeoutError',
    }
)
T = TypeVar('T')


class PineconeVectorStore(VectorIndex):
    """A Pinecone-backed `VectorIndex`, using one namespace per version.

    Namespaces give version isolation without a separate physical index per
    version: writes to an inactive version's namespace never affect queries
    scoped to the active version's namespace.
    """

    def __init__(
        self,
        *,
        index_name: str,
        api_key: Optional[str] = None,
        batch_size: int = 100,
        client: Optional[Any] = None,
    ) -> None:
        """Initializes a PineconeVectorStore.

        Args:
            index_name: The name of an existing Pinecone index (this class
                does not create indexes -- their vector dimension/metric must
                already match the configured embedder).
            api_key: Optional explicit API key; otherwise resolved by the
                `pinecone` client from the `PINECONE_API_KEY` environment
                variable. Never logged or included in provenance.
            batch_size: Records per `upsert` request.
            client: A pre-built Pinecone `Index` handle (or any object
                exposing `.upsert`/`.delete`/`.describe_index_stats`) to use
                instead of constructing one -- bypasses the `pinecone`
                dependency check entirely, which is how tests exercise this
                class without it installed.

        Raises:
            OptionalDependencyError: `pinecone` is not installed and no
                `client` was given.
        """
        self._index_name = index_name
        self._batch_size = batch_size

        if client is not None:
            self._index = client
        else:
            if Pinecone is None:
                raise OptionalDependencyError(
                    package='pinecone', extra='rag-pinecone', feature='PineconeVectorStore'
                )
            self._index = Pinecone(api_key=api_key).Index(index_name)

    @property
    def target_index_name(self) -> str:
        return self._index_name

    @property
    def store_type(self) -> str:
        return 'pinecone'

    def upsert(self, records: Iterable[VectorRecord], version: str) -> UpsertResult:
        materialized = list(records)
        if not materialized:
            return UpsertResult(upserted_count=0, version=version)

        try:
            for batch in _batched(materialized, self._batch_size):
                vectors = [_to_pinecone_vector(record) for record in batch]
                self._index.upsert(vectors=vectors, namespace=version)
        except Exception as exc:
            raise self._classify(exc) from exc
        return UpsertResult(upserted_count=len(materialized), version=version)

    def delete_document(self, document_id: str, version: str) -> None:
        try:
            self._index.delete(filter={'document_id': {'$eq': document_id}}, namespace=version)
        except Exception as exc:
            # Serverless Pinecone indexes don't support metadata-filtered delete
            # (only pod-based ones do); surface that as a clear, non-transient error.
            if 'serverless' in str(exc).lower() or 'not supported' in str(exc).lower():
                raise VectorStoreError(
                    f'delete_document by metadata filter is not supported on this Pinecone '
                    f'index (serverless indexes require pod-based indexes for filtered '
                    f'delete): {exc}'
                ) from exc
            raise self._classify(exc) from exc

    def validate_version(self, version: str) -> ValidationResult:
        try:
            stats = self._index.describe_index_stats()
        except Exception as exc:
            raise self._classify(exc) from exc

        chunk_count = _namespace_vector_count(stats, version)
        return ValidationResult(
            valid=chunk_count > 0,
            version=version,
            actual_chunk_count=chunk_count,
            details=f'{chunk_count} vector(s) in namespace {version!r} (per describe_index_stats)',
        )

    def query(
        self,
        embedding: Iterable[float],
        version: str,
        *,
        top_k: int = 5,
        metadata_filter: Optional[dict[str, Any]] = None,
        query_text: Optional[str] = None,  # unused: this Pinecone adapter is dense-vector-only
    ) -> list[QueryMatch]:
        try:
            response = self._index.query(
                vector=list(embedding),
                top_k=top_k,
                namespace=version,
                include_metadata=True,
                filter=metadata_filter,
            )
        except Exception as exc:
            raise self._classify(exc) from exc
        return [_to_query_match(match) for match in _response_matches(response)]

    @staticmethod
    def _classify(exc: Exception) -> RagError:
        if type(exc).__name__ in _TRANSIENT_EXCEPTION_NAMES:
            return TransientVectorStoreError(str(exc))
        status_code = getattr(exc, 'status', None) or getattr(exc, 'status_code', None)
        if isinstance(status_code, int) and (status_code == 429 or status_code >= 500):
            return TransientVectorStoreError(str(exc))
        return VectorStoreError(str(exc))


def _namespace_vector_count(stats: Any, version: str) -> int:
    namespaces = getattr(stats, 'namespaces', None)
    if namespaces is None and isinstance(stats, dict):
        namespaces = stats.get('namespaces')
    namespaces = namespaces or {}

    namespace_stats = namespaces.get(version)
    if namespace_stats is None:
        return 0
    vector_count = getattr(namespace_stats, 'vector_count', None)
    if vector_count is None and isinstance(namespace_stats, dict):
        vector_count = namespace_stats.get('vector_count')
    return int(vector_count) if vector_count is not None else 0


def _batched(items: list[T], size: int) -> Iterator[list[T]]:
    for start in range(0, len(items), size):
        yield items[start : start + size]


def _to_pinecone_vector(record: VectorRecord) -> dict[str, Any]:
    # Built via an explicit dict() + assignment rather than a `{**record.metadata,
    # 'document_id': ..., 'content': ...}` literal: mypy infers a dict literal's
    # value type from *all* its keys, including the two str-typed ones, and then
    # rejects the unpacked dict[str, Any] as incompatible with that narrowed type.
    metadata: dict[str, Any] = dict(record.metadata)
    metadata['document_id'] = record.document_id
    metadata['content'] = record.content
    return {'id': record.chunk_id, 'values': list(record.embedding), 'metadata': metadata}


def _response_matches(response: Any) -> list[Any]:
    matches = getattr(response, 'matches', None)
    if matches is None and isinstance(response, dict):
        matches = response.get('matches')
    return list(matches or [])


def _to_query_match(match: Any) -> QueryMatch:
    metadata = getattr(match, 'metadata', None)
    if metadata is None and isinstance(match, dict):
        metadata = match.get('metadata')
    metadata = dict(metadata or {})
    content = metadata.pop('content', '')
    document_id = metadata.pop('document_id', '')

    match_id = getattr(match, 'id', None)
    if match_id is None and isinstance(match, dict):
        match_id = match.get('id')

    score = getattr(match, 'score', None)
    if score is None and isinstance(match, dict):
        score = match.get('score')

    return QueryMatch(
        chunk_id=match_id or '',
        document_id=document_id,
        content=content,
        score=float(score or 0.0),
        metadata=metadata,
    )
