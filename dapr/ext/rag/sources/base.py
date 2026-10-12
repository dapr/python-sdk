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
from typing import Iterator, Optional

from dapr.ext.rag.models import SourceDocument, SourceMetadata, SourceProvider


class DocumentSource(ABC):
    """A pluggable source of documents to ingest (S3, Azure Blob, ...).

    Implementations must produce `SourceDocument`/`SourceMetadata` values that
    are normalized the same way regardless of provider, so `pipeline.py`
    contains no provider-specific branching. All methods perform I/O and must
    only ever be called from within a workflow activity, never from the
    orchestrator.
    """

    @property
    @abstractmethod
    def provider(self) -> SourceProvider:
        """Which provider this source implements."""

    @abstractmethod
    def list_documents(self, prefix: Optional[str] = None) -> Iterator[SourceDocument]:
        """Lists documents under `prefix` (or this source's configured prefix).

        Implementations must page through the underlying API internally and
        yield one `SourceDocument` at a time, so a caller can persist results
        incrementally instead of holding an entire large corpus in memory.

        Args:
            prefix: Overrides the source's configured prefix for this call.

        Yields:
            One `SourceDocument` per discovered object, in provider-listing
            order (typically lexicographic by key/name, but callers should
            not depend on a specific order).

        Raises:
            TransientSourceError: The listing call failed transiently.
        """

    @abstractmethod
    def get_document(self, document_id: str) -> bytes:
        """Downloads a document's full content.

        Args:
            document_id: A `document_id` previously returned by
                `list_documents`.

        Returns:
            The document's raw bytes.

        Raises:
            SourceNotFoundError: The document no longer exists.
            SourceAccessDeniedError: The credentials lack access.
            TransientSourceError: The download failed transiently.
        """

    @abstractmethod
    def get_metadata(self, document_id: str) -> SourceMetadata:
        """Fetches a document's current metadata without downloading its content.

        Used to detect whether a document changed between discovery and
        download (a different ETag/version than what was recorded in the
        manifest).

        Args:
            document_id: A `document_id` previously returned by
                `list_documents`.

        Returns:
            The document's current `SourceMetadata`.

        Raises:
            SourceNotFoundError: The document no longer exists.
            SourceAccessDeniedError: The credentials lack access.
            TransientSourceError: The metadata call failed transiently.
        """

    def close(self) -> None:
        """Releases any held resources (connections, sessions). Optional to override."""
