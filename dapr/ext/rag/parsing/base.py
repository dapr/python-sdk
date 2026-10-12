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
from typing import Any

from dapr.ext.rag.fingerprints import compute_config_hash
from dapr.ext.rag.models import Document, SourceDocument


class DocumentParser(ABC):
    """Parses a downloaded document's raw bytes into `Document` units.

    The spec this package implements sketches `parse(content, metadata:
    SourceMetadata)`; this takes the richer `SourceDocument` instead (it
    carries both identity -- `name`, used for file-type detection -- and the
    point-in-time `SourceMetadata`, e.g. `content_type`), so a parser has
    everything it needs without a second lookup.
    """

    @property
    @abstractmethod
    def parser_type(self) -> str:
        """A short, stable name identifying this parser for provenance (e.g. 'unstructured')."""

    @abstractmethod
    def parse(self, content: bytes, document: SourceDocument) -> list[Document]:
        """Parses raw document bytes into one or more `Document` units.

        Args:
            content: The document's raw bytes.
            document: The `SourceDocument` this content was downloaded for
                (for filename/content-type-based format detection).

        Returns:
            One or more parsed `Document`s (e.g. one per page or section).

        Raises:
            UnsupportedDocumentError: This format isn't supported.
            DocumentParseError: The content could not be parsed (corrupt).
        """

    def config(self) -> dict[str, Any]:
        """Behavior-affecting configuration to fold into the parser's fingerprint.

        Must be JSON-serializable and must not include secrets. The default
        implementation returns an empty config; override when a parser has
        settings that change its output (e.g. a strategy or language list).
        """
        return {}

    def config_fingerprint(self) -> str:
        """A stable hash of `config()`, used to build the pipeline fingerprint."""
        return compute_config_hash(self.config())
