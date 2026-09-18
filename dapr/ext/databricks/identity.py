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

Deterministic Dapr Workflow instance-ID derivation for the Databricks sink.

This module is the crux of the sink's retry-safety: the same logical record
must always sanitize to the same instance ID, across processes and across
Lakeflow retries of the same micro-batch, so ``scheduling.ensure_workflow_scheduled``
can recognize "already handled" via a plain lookup instead of guessing.
"""

from __future__ import annotations

import hashlib
import re
from typing import Optional, Sequence

from dapr.ext.databricks._typing import InstanceIdFactory, RowLike
from dapr.ext.databricks.exceptions import MissingBusinessKeyError

# Dapr workflow instance IDs may only contain alphanumeric characters,
# underscores, and dashes (see the Dapr Workflow "manage workflows" docs).
_CLEAN_SEGMENT_RE = re.compile(r'[A-Za-z0-9_-]+')

# Dapr does not publish a maximum instance-ID length. These bounds are this
# extension's own conservative safety margin, keeping generated IDs short
# enough to stay friendly to every backing actor/state store Dapr might use.
_MAX_CLEAN_SEGMENT_LENGTH = 80
_MAX_INSTANCE_ID_LENGTH = 128
_HASH_LENGTH = 32


def sanitize_segment(raw: str) -> str:
    """Returns a Dapr-instance-ID-safe segment derived deterministically from ``raw``.

    A segment that is already short and composed entirely of
    ``[A-Za-z0-9_-]`` is returned unchanged, so common business keys (order
    numbers, UUIDs, account IDs) stay human-readable in the resulting
    instance ID. Anything else — Unicode, punctuation, empty strings, or
    values over ``_MAX_CLEAN_SEGMENT_LENGTH`` chars — is replaced by a SHA-256
    hex digest of its UTF-8 encoding. Hashing the *whole* segment (rather than
    stripping individual bad characters) avoids collisions that a
    character-by-character replacement could introduce, e.g. between "a/b"
    and "a-b" once both map to the same cleaned output.

    Args:
        raw: The unsanitized segment value.

    Returns:
        A non-empty string containing only alphanumeric characters,
        underscores, and dashes.
    """
    is_clean = (
        len(raw) <= _MAX_CLEAN_SEGMENT_LENGTH and _CLEAN_SEGMENT_RE.fullmatch(raw) is not None
    )
    if is_clean:
        return raw
    return hashlib.sha256(raw.encode('utf-8')).hexdigest()[:_HASH_LENGTH]


def _extract_single_field(row: RowLike, field: str) -> str:
    """Reads one required, non-null field from a row as a string business key."""
    row_dict = row.asDict()
    if field not in row_dict:
        raise MissingBusinessKeyError(f"id field '{field}' is not present on this row")
    value = row_dict[field]
    if value is None:
        raise MissingBusinessKeyError(f"id field '{field}' is null on this row")
    return str(value)


def extract_business_key(
    row: RowLike,
    batch_id: int,
    *,
    id_field: Optional[str],
    id_fields: Optional[Sequence[str]],
    instance_id_factory: Optional[InstanceIdFactory],
) -> Optional[str]:
    """Derives the business-key component of a workflow instance ID from a row.

    Exactly one of ``id_field``, ``id_fields``, or ``instance_id_factory`` is
    expected to be set (``WorkflowSinkConfig`` enforces this at configuration
    time); if none are set, ``None`` is returned and the caller falls back to
    batch/record-position identity.

    Args:
        row: The Spark row for a single record.
        batch_id: The Lakeflow micro-batch ID, passed through to a custom
            ``instance_id_factory``.
        id_field: Single business-key column name, if configured.
        id_fields: Composite business-key column names, if configured.
        instance_id_factory: Escape hatch that computes the business-key
            component directly from the row; still namespaced, sanitized, and
            composed with ``generation`` like any other business key.

    Returns:
        The raw (not yet sanitized) business-key string, or ``None`` if no
        business-key strategy is configured.

    Raises:
        MissingBusinessKeyError: A configured ``id_field``/``id_fields``
            column is absent or null on this row.
    """
    if instance_id_factory is not None:
        return str(instance_id_factory(row, batch_id))
    if id_field is not None:
        return _extract_single_field(row, id_field)
    if id_fields:
        key_components = [_extract_single_field(row, field) for field in id_fields]
        return '_'.join(key_components)
    return None


def derive_instance_id(
    *,
    namespace: str,
    sink_name: str,
    generation: str,
    business_key: Optional[str],
    batch_id: int,
    record_index: int,
) -> str:
    """Composes the deterministic Dapr Workflow instance ID for one record.

    The template is ``<namespace>-<sink>-<generation>-<business_key>`` when a
    business key is available, or ``<namespace>-<sink>-<generation>-<batch_id>-<record_index>``
    otherwise. ``generation`` is always part of the identity: this is what
    lets a full pipeline refresh (which restarts ``batch_id`` from 0 and can
    replay already-handled business keys) be given a fresh, non-colliding
    identity space simply by bumping ``generation`` — see the module README
    for the full explanation of full-refresh semantics.

    Args:
        namespace: Logical partition for this sink's workflow identities
            (e.g. a business domain like ``"orders"``).
        sink_name: The registered sink name.
        generation: Identity epoch. Bump this to intentionally replay
            business actions after a full refresh; keep it stable for normal
            retries to dedupe correctly.
        business_key: Pre-extracted business key, or ``None`` to fall back to
            batch/record-position identity.
        batch_id: The Lakeflow micro-batch ID.
        record_index: The record's 0-based position within the micro-batch,
            used only when ``business_key`` is ``None``.

    Returns:
        A stable, Dapr-instance-ID-safe string: the same logical record
        always produces the same output.
    """
    namespace_segment = sanitize_segment(namespace)
    sink_segment = sanitize_segment(sink_name)
    generation_segment = sanitize_segment(generation)

    if business_key is not None:
        key_segment = sanitize_segment(business_key)
        instance_id = f'{namespace_segment}-{sink_segment}-{generation_segment}-{key_segment}'
    else:
        instance_id = (
            f'{namespace_segment}-{sink_segment}-{generation_segment}-{batch_id}-{record_index}'
        )

    if len(instance_id) <= _MAX_INSTANCE_ID_LENGTH:
        return instance_id

    # Individually-clean segments can still add up to an over-long ID (e.g. a
    # long but valid namespace/sink pair). Collapse deterministically instead
    # of naively truncating the composed string, which could chop off the
    # record-specific suffix entirely and collide every record in the sink
    # onto the same truncated prefix. The digest (derived from the full,
    # per-record instance_id) is always kept intact; only the human-readable
    # prefix is shortened to make room.
    digest = hashlib.sha256(instance_id.encode('utf-8')).hexdigest()[:_HASH_LENGTH]
    prefix = f'{namespace_segment}-{sink_segment}-{generation_segment}'
    max_prefix_length = _MAX_INSTANCE_ID_LENGTH - len(digest) - 1  # 1 for the joining '-'
    if max_prefix_length <= 0:
        return digest
    return f'{prefix[:max_prefix_length]}-{digest}'
