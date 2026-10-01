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

import json
import re
from typing import Any, Callable, Iterable, Optional

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
    import psycopg
except ImportError:  # pragma: no cover - exercised only without psycopg installed
    psycopg = None  # type: ignore[assignment]

_SAFE_IDENTIFIER = re.compile(r'^[A-Za-z_][A-Za-z0-9_]*$')
_TRANSIENT_EXCEPTION_NAMES = frozenset(
    {'OperationalError', 'InterfaceError', 'AdminShutdown', 'ConnectionTimeout'}
)


class PgVectorStore(VectorIndex):
    """A pgvector-backed `VectorIndex`.

    All versions of one `collection` share a single physical table, scoped by
    a `version` column with a `(version, chunk_id)` primary key -- so writes
    are idempotent per version, queries can be scoped to exactly one version,
    and no separate physical database or table is needed per version. Schema
    (the table, its `vector` extension, and a supporting index) is created on
    first use if missing, and never drops or alters an existing table.
    """

    def __init__(
        self,
        *,
        connection_string: Optional[str] = None,
        collection: str,
        embedding_dimensions: Optional[int] = None,
        connection_factory: Optional[Callable[[], Any]] = None,
    ) -> None:
        """Initializes a PgVectorStore.

        Args:
            connection_string: A libpq connection string/URI. Required
                unless `connection_factory` is given.
            collection: A logical name for this index; mapped to the table
                `rag_chunks_{collection}` (collection must match
                `^[A-Za-z_][A-Za-z0-9_]*$`, since SQL identifiers can't be
                parameterized).
            embedding_dimensions: The embedding vector width, used to create
                the table's `vector(n)` column. If omitted, inferred from the
                first batch passed to `upsert`.
            connection_factory: A zero-argument callable returning a
                psycopg-connection-like context manager, used instead of
                `psycopg.connect(connection_string)` -- bypasses the
                `psycopg` dependency check entirely, which is how tests
                exercise this class without it installed. A new connection is
                requested per call, which keeps this class safe to share
                across concurrently-running activities without pooling.

        Raises:
            OptionalDependencyError: `psycopg` is not installed and no
                `connection_factory` was given.
            ValueError: `collection` isn't a safe SQL identifier, or neither
                `connection_string` nor `connection_factory` was given.
        """
        if not _SAFE_IDENTIFIER.match(collection):
            raise ValueError(
                f'collection={collection!r} must match {_SAFE_IDENTIFIER.pattern!r} to be used '
                'as part of a SQL table name.'
            )
        self._collection = collection
        self._table = f'rag_chunks_{collection}'
        self._embedding_dimensions = embedding_dimensions
        self._schema_ready = False

        if connection_factory is not None:
            self._connection_factory = connection_factory
        else:
            if psycopg is None:
                raise OptionalDependencyError(
                    package='psycopg', extra='rag-pgvector', feature='PgVectorStore'
                )
            if not connection_string:
                raise ValueError('PgVectorStore requires connection_string or connection_factory.')
            self._connection_factory = lambda: psycopg.connect(connection_string)

    @property
    def target_index_name(self) -> str:
        return self._collection

    @property
    def store_type(self) -> str:
        return 'pgvector'

    def upsert(self, records: Iterable[VectorRecord], version: str) -> UpsertResult:
        materialized = list(records)
        if not materialized:
            return UpsertResult(upserted_count=0, version=version)

        dimensions = self._embedding_dimensions or len(materialized[0].embedding)
        try:
            with self._connection_factory() as conn:
                self._ensure_schema(conn, dimensions)
                with conn.cursor() as cur:
                    for record in materialized:
                        cur.execute(
                            f'INSERT INTO {self._table} '  # noqa: S608 - table name is identifier-validated above
                            '(chunk_id, version, document_id, content, embedding, metadata) '
                            'VALUES (%s, %s, %s, %s, %s::vector, %s) '
                            'ON CONFLICT (version, chunk_id) DO UPDATE SET '
                            'content = EXCLUDED.content, embedding = EXCLUDED.embedding, '
                            'metadata = EXCLUDED.metadata',
                            (
                                record.chunk_id,
                                version,
                                record.document_id,
                                record.content,
                                _to_vector_literal(record.embedding),
                                json.dumps(record.metadata),
                            ),
                        )
                conn.commit()
        except Exception as exc:
            raise self._classify(exc) from exc
        return UpsertResult(upserted_count=len(materialized), version=version)

    def delete_document(self, document_id: str, version: str) -> None:
        try:
            with self._connection_factory() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        f'DELETE FROM {self._table} WHERE version = %s AND document_id = %s',  # noqa: S608
                        (version, document_id),
                    )
                conn.commit()
        except Exception as exc:
            raise self._classify(exc) from exc

    def validate_version(self, version: str) -> ValidationResult:
        try:
            with self._connection_factory() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        f'SELECT COUNT(*), COUNT(DISTINCT document_id) FROM {self._table} '  # noqa: S608
                        'WHERE version = %s',
                        (version,),
                    )
                    row = cur.fetchone()
        except Exception as exc:
            raise self._classify(exc) from exc

        chunk_count, document_count = (row[0], row[1]) if row else (0, 0)
        return ValidationResult(
            valid=chunk_count > 0,
            version=version,
            actual_document_count=document_count,
            actual_chunk_count=chunk_count,
            details=f'{chunk_count} chunk(s) across {document_count} document(s) in version {version!r}',
        )

    def query(
        self,
        embedding: Iterable[float],
        version: str,
        *,
        top_k: int = 5,
        metadata_filter: Optional[dict[str, Any]] = None,
        query_text: Optional[str] = None,  # unused: pgvector search here is vector-only
    ) -> list[QueryMatch]:
        vector_literal = _to_vector_literal(embedding)
        where_clauses = ['version = %s']
        params: list[Any] = [version]
        if metadata_filter:
            where_clauses.append('metadata @> %s::jsonb')
            params.append(json.dumps(metadata_filter))

        query = (
            'SELECT chunk_id, document_id, content, metadata, 1 - (embedding <=> %s::vector) AS score '
            f'FROM {self._table} WHERE {" AND ".join(where_clauses)} '  # noqa: S608
            'ORDER BY embedding <=> %s::vector LIMIT %s'
        )
        try:
            with self._connection_factory() as conn:
                with conn.cursor() as cur:
                    cur.execute(query, [vector_literal, *params, vector_literal, top_k])
                    rows = cur.fetchall()
        except Exception as exc:
            raise self._classify(exc) from exc

        return [
            QueryMatch(
                chunk_id=row[0],
                document_id=row[1],
                content=row[2] or '',
                score=float(row[4]),
                metadata=_load_metadata(row[3]),
            )
            for row in rows
        ]

    def close(self) -> None:
        pass  # a new connection is opened and closed per call; nothing to hold open

    def _ensure_schema(self, conn: Any, dimensions: int) -> None:
        if self._schema_ready:
            return
        with conn.cursor() as cur:
            try:
                cur.execute('CREATE EXTENSION IF NOT EXISTS vector')
            except Exception:
                # Best-effort: the extension may already exist, or this role may lack
                # CREATE EXTENSION privilege while an admin already installed it.
                conn.rollback()
            cur.execute(
                f'CREATE TABLE IF NOT EXISTS {self._table} ('  # noqa: S608
                'chunk_id TEXT NOT NULL, '
                'version TEXT NOT NULL, '
                'document_id TEXT NOT NULL, '
                'content TEXT, '
                f'embedding VECTOR({dimensions}), '
                'metadata JSONB, '
                'created_at TIMESTAMPTZ NOT NULL DEFAULT now(), '
                'PRIMARY KEY (version, chunk_id))'
            )
            cur.execute(
                f'CREATE INDEX IF NOT EXISTS {self._table}_document_idx '  # noqa: S608
                f'ON {self._table} (version, document_id)'
            )
        conn.commit()
        self._schema_ready = True

    @staticmethod
    def _classify(exc: Exception) -> RagError:
        if type(exc).__name__ in _TRANSIENT_EXCEPTION_NAMES:
            return TransientVectorStoreError(str(exc))
        return VectorStoreError(str(exc))


def _to_vector_literal(embedding: Iterable[float]) -> str:
    """Formats an embedding as a pgvector input literal, e.g. '[0.1,0.2]'.

    Avoids a hard dependency on the separate `pgvector` Python package (which
    exists mainly to register numpy-array adapters); a plain literal string
    cast with `::vector` is all pgvector's wire format needs.
    """
    return '[' + ','.join(repr(float(value)) for value in embedding) + ']'


def _load_metadata(raw: Any) -> dict[str, Any]:
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, str) and raw:
        return json.loads(raw)
    return {}
