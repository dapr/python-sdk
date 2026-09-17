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

# All Dapr state access for the pipeline goes through this one class, called
# both from within workflow activities (during ingestion) and directly by
# client-side code such as `pipeline.get_status()` (a plain query, exactly
# like `DaprWorkflowClient.get_workflow_state()` -- not part of any
# orchestrator replay, so it's fine for it to talk to Dapr state directly).
#
# Key schema (all under the `rag:` prefix):
#   rag:manifest:{pipeline_id}:{version}:meta          -- ManifestSummary + page_count
#   rag:manifest:{pipeline_id}:{version}:page:{n}       -- one page of DocumentWorkItem
#   rag:completion:{pipeline_id}:{version}:{document_id} -- CompletionRecord (idempotency)
#   rag:embed-progress:{pipeline_id}:{version}:{document_id} -- EmbedProgressRecord
#   rag:attempts:{pipeline_id}:{version}:{document_id}  -- {"attempts": N}
#   rag:status:{pipeline_id}:{version}                  -- PipelineStatus
#   rag:activation:{pipeline_id}                         -- ActivationRecord (ETag-guarded)

from __future__ import annotations

import dataclasses
import json
import logging
from typing import Any, Iterator, Optional, Sequence, TypeVar

import grpc

from dapr.clients import DaprClient
from dapr.ext.rag.errors import ActivationConflictError
from dapr.ext.rag.models import (
    ActivationRecord,
    CompletionRecord,
    DocumentWorkItem,
    EmbedProgressRecord,
    ManifestSummary,
    PipelineStatus,
)

logger = logging.getLogger(__name__)

T = TypeVar('T')


class PipelineStateStore:
    """Reads and writes all `dapr.ext.rag` pipeline state for one Dapr state store."""

    def __init__(self, *, state_store_name: str, dapr_client: Optional[DaprClient] = None) -> None:
        """Initializes a PipelineStateStore.

        Args:
            state_store_name: The Dapr state store component name.
            dapr_client: A `DaprClient` to reuse; a new one is created (and
                owned/closed by this instance) when omitted.
        """
        self._state_store_name = state_store_name
        self._owns_client = dapr_client is None
        self._client = dapr_client or DaprClient()

    def close(self) -> None:
        """Closes the underlying `DaprClient`, if this instance created it."""
        if self._owns_client:
            self._client.close()

    # -- manifest ---------------------------------------------------------

    def write_manifest(
        self,
        *,
        pipeline_id: str,
        version: str,
        documents: Sequence[DocumentWorkItem],
        page_size: int,
        manifest_hash: str,
        created_at: str,
    ) -> ManifestSummary:
        """Persists a manifest in fixed-size pages and returns its summary.

        Paging keeps any single state value small regardless of corpus size,
        and lets `read_manifest_page` double as the fan-out batch source (one
        page read == one bounded batch of concurrent `process_document`
        calls).
        """
        pages = list(_chunked(documents, page_size))
        for page_index, page in enumerate(pages):
            self._save_json(
                self._manifest_page_key(pipeline_id, version, page_index),
                [dataclasses.asdict(item) for item in page],
            )
        summary = ManifestSummary(
            version=version,
            total_documents=len(documents),
            manifest_hash=manifest_hash,
            page_size=page_size,
            created_at=created_at,
        )
        meta = {**dataclasses.asdict(summary), 'page_count': len(pages)}
        self._save_json(self._manifest_meta_key(pipeline_id, version), meta)
        return summary

    def read_manifest_meta(self, *, pipeline_id: str, version: str) -> Optional[dict[str, Any]]:
        return self._get_json(self._manifest_meta_key(pipeline_id, version))

    def read_manifest_page(
        self, *, pipeline_id: str, version: str, page_index: int
    ) -> list[DocumentWorkItem]:
        raw = self._get_json(self._manifest_page_key(pipeline_id, version, page_index)) or []
        return [DocumentWorkItem(**item) for item in raw]

    # -- per-document completion (idempotency) -----------------------------

    def read_completion(
        self, *, pipeline_id: str, version: str, document_id: str
    ) -> Optional[CompletionRecord]:
        raw = self._get_json(self._completion_key(pipeline_id, version, document_id))
        return CompletionRecord.from_dict(raw) if raw is not None else None

    def write_completion(self, *, pipeline_id: str, version: str, record: CompletionRecord) -> None:
        self._save_json(
            self._completion_key(pipeline_id, version, record.document_id), record.to_dict()
        )

    # -- per-document embedding progress (batch-level resumability) --------

    def read_embed_progress(
        self, *, pipeline_id: str, version: str, document_id: str
    ) -> Optional[EmbedProgressRecord]:
        raw = self._get_json(self._embed_progress_key(pipeline_id, version, document_id))
        return EmbedProgressRecord.from_dict(raw) if raw is not None else None

    def write_embed_progress(
        self, *, pipeline_id: str, version: str, record: EmbedProgressRecord
    ) -> None:
        self._save_json(
            self._embed_progress_key(pipeline_id, version, record.document_id), record.to_dict()
        )

    # -- per-document attempt counts (retry metric) -------------------------

    def increment_attempt_count(self, *, pipeline_id: str, version: str, document_id: str) -> int:
        """Increments and returns the number of times this document has been attempted.

        Not etag-guarded: Dapr Workflow retries a given activity task
        sequentially, never concurrently, so there is exactly one writer at a
        time for a given document's counter.
        """
        key = self._attempts_key(pipeline_id, version, document_id)
        current = self._get_json(key) or {'attempts': 0}
        attempts = int(current.get('attempts', 0)) + 1
        self._save_json(key, {'attempts': attempts})
        return attempts

    # -- pipeline status -----------------------------------------------------

    def read_status(self, *, pipeline_id: str, version: str) -> Optional[PipelineStatus]:
        raw = self._get_json(self._status_key(pipeline_id, version))
        return PipelineStatus.from_dict(raw) if raw is not None else None

    def write_status(self, status: PipelineStatus) -> None:
        self._save_json(
            self._status_key(status.pipeline_id, status.requested_version), status.to_dict()
        )

    # -- activation (ETag-guarded active-version pointer) --------------------

    def read_activation(self, pipeline_id: str) -> tuple[Optional[ActivationRecord], Optional[str]]:
        """Reads the active-version pointer and its current ETag.

        Returns:
            `(None, etag_or_none)` if no version has ever been activated for
            this pipeline, else `(record, etag)`. The etag (which may be an
            empty string for some state stores' "key doesn't exist yet"
            case) must be threaded back into `write_activation` to detect a
            concurrent activation.
        """
        response = self._client.get_state(
            store_name=self._state_store_name,
            key=self._activation_key(pipeline_id),
            state_metadata={'consistency': 'strong'},
        )
        if not response.data:
            return None, response.etag
        return ActivationRecord.from_dict(_decode_json(response.data)), response.etag

    def write_activation(self, record: ActivationRecord, *, etag: Optional[str]) -> None:
        """Writes the active-version pointer, conditioned on `etag`.

        Args:
            record: The new activation record to write.
            etag: The etag last read via `read_activation` for this
                pipeline_id (or `None`/empty if none was ever activated).

        Raises:
            ActivationConflictError: Another writer updated the pointer
                after `etag` was read (Dapr returns `ABORTED`).
        """
        try:
            self._client.save_state(
                store_name=self._state_store_name,
                key=self._activation_key(record.pipeline_id),
                value=json.dumps(record.to_dict()),
                etag=etag or None,
            )
        except grpc.RpcError as exc:
            if exc.code() == grpc.StatusCode.ABORTED:
                raise ActivationConflictError(
                    f'Active-version pointer for pipeline {record.pipeline_id!r} was updated '
                    'concurrently; retry will re-read the current pointer.'
                ) from exc
            raise

    # -- key schema ------------------------------------------------------

    @staticmethod
    def _manifest_meta_key(pipeline_id: str, version: str) -> str:
        return f'rag:manifest:{pipeline_id}:{version}:meta'

    @staticmethod
    def _manifest_page_key(pipeline_id: str, version: str, page_index: int) -> str:
        return f'rag:manifest:{pipeline_id}:{version}:page:{page_index}'

    @staticmethod
    def _completion_key(pipeline_id: str, version: str, document_id: str) -> str:
        return f'rag:completion:{pipeline_id}:{version}:{document_id}'

    @staticmethod
    def _embed_progress_key(pipeline_id: str, version: str, document_id: str) -> str:
        return f'rag:embed-progress:{pipeline_id}:{version}:{document_id}'

    @staticmethod
    def _attempts_key(pipeline_id: str, version: str, document_id: str) -> str:
        return f'rag:attempts:{pipeline_id}:{version}:{document_id}'

    @staticmethod
    def _status_key(pipeline_id: str, version: str) -> str:
        return f'rag:status:{pipeline_id}:{version}'

    @staticmethod
    def _activation_key(pipeline_id: str) -> str:
        return f'rag:activation:{pipeline_id}'

    # -- JSON helpers ------------------------------------------------------
    # DaprClient.save_state/get_state move only bytes/str -- see
    # dapr/clients/grpc/_state.py -- so JSON (de)serialization happens here,
    # once, rather than at every call site.

    def _get_json(self, key: str) -> Optional[Any]:
        response = self._client.get_state(store_name=self._state_store_name, key=key)
        if not response.data:
            return None
        return _decode_json(response.data)

    def _save_json(self, key: str, value: Any) -> None:
        self._client.save_state(store_name=self._state_store_name, key=key, value=json.dumps(value))


def _decode_json(data: Any) -> Any:
    text = data.decode('utf-8') if isinstance(data, bytes) else data
    return json.loads(text)


def _chunked(items: Sequence[T], size: int) -> Iterator[list[T]]:
    for start in range(0, len(items), size):
        yield list(items[start : start + size])
