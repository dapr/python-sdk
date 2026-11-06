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

# Deterministic hashing for stable IDs and change detection.
#
# Every function here is a pure function of its inputs: no randomness, no
# clock reads, and no dependence on Python's per-process-randomized `hash()`.
# That makes them safe to call from a workflow orchestrator directly, and
# guarantees a replay or a retry recomputes the same IDs. SHA-256 is used
# throughout (rather than e.g. `uuid.uuid5`) so the exact fields folded into
# an ID are visible and debuggable from the source below, matching how the
# spec describes chunk-ID derivation as a list of named fields.

from __future__ import annotations

import hashlib
import json
from typing import Any, Iterable, Mapping

# ASCII Unit Separator: joins hash inputs without the field-boundary ambiguity
# a plain string like '|' or ':' would have if a field's own value contained it.
_FIELD_SEPARATOR = '\x1f'


def _stable_digest(*parts: str) -> str:
    return hashlib.sha256(_FIELD_SEPARATOR.join(parts).encode('utf-8')).hexdigest()


def compute_content_hash(data: bytes) -> str:
    """Hashes raw document bytes for change detection and provenance.

    Args:
        data: The document's raw bytes, as downloaded from its source.

    Returns:
        A hex SHA-256 digest of `data`.
    """
    return hashlib.sha256(data).hexdigest()


def compute_config_hash(config: Mapping[str, Any]) -> str:
    """Hashes an adapter's configuration (e.g. a parser's or splitter's).

    Args:
        config: A JSON-serializable mapping describing the adapter's
            behavior-affecting settings (e.g. `{'chunk_size': 1000}`). Must
            not include secrets (API keys, connection strings) -- this hash
            is stored in provenance records and pipeline state.

    Returns:
        A hex SHA-256 digest, stable regardless of key order.
    """
    canonical = json.dumps(config, sort_keys=True, separators=(',', ':'), default=str)
    return hashlib.sha256(canonical.encode('utf-8')).hexdigest()


def compute_pipeline_fingerprint(
    *,
    parser_config_hash: str,
    splitter_config_hash: str,
    embedding_model: str,
    embedding_config_hash: str,
) -> str:
    """Fingerprints the processing recipe applied to every document.

    Used alongside a document's own content hash to decide whether prior
    work for that document is still valid: changing the parser, splitter, or
    embedding configuration changes this fingerprint, which invalidates prior
    completion records even though the source content hasn't changed.

    Returns:
        A hex SHA-256 digest of the four inputs.
    """
    return _stable_digest(
        parser_config_hash, splitter_config_hash, embedding_model, embedding_config_hash
    )


def compute_chunk_id(
    *,
    source_document_id: str,
    source_content_hash: str,
    parser_config_hash: str,
    splitter_config_hash: str,
    chunk_ordinal: int,
    chunk_content_hash: str,
    embedding_model: str,
) -> str:
    """Derives a stable chunk ID, per the spec's field list.

    A replay or a retry of the same document, under the same configuration,
    produces the same chunk IDs -- which is what makes vector upserts
    idempotent. Changing any input (new content, new parser/splitter config,
    a different embedding model) produces different IDs, so the new content
    is written under new IDs rather than silently overwriting stale ones with
    a different provenance.

    Returns:
        A hex SHA-256 digest of the seven inputs, suitable as a vector ID.
    """
    return _stable_digest(
        source_document_id,
        source_content_hash,
        parser_config_hash,
        splitter_config_hash,
        str(chunk_ordinal),
        chunk_content_hash,
        embedding_model,
    )


def compute_manifest_hash(document_ids: Iterable[str]) -> str:
    """Hashes the (sorted) set of document IDs discovered for a version.

    Sorting first makes the hash independent of listing/pagination order, so
    two discovery activities that see the same documents in a different
    order still agree on the manifest hash.

    Args:
        document_ids: The `document_id` of every document in the manifest.

    Returns:
        A hex SHA-256 digest of the sorted document IDs.
    """
    return _stable_digest(*sorted(document_ids))
