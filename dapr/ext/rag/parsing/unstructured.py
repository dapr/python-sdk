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

import io
from pathlib import Path
from typing import Any, Callable, Optional, Sequence

from dapr.ext.rag.errors import (
    DocumentParseError,
    OptionalDependencyError,
    UnsupportedDocumentError,
)
from dapr.ext.rag.models import Document, SourceDocument
from dapr.ext.rag.parsing.base import DocumentParser

# See dapr/ext/rag/AGENTS.md for why the optional-dependency guard lives here,
# per adapter module, rather than once in dapr/ext/rag/__init__.py.
try:
    from unstructured.partition.auto import partition as _default_partition
except ImportError:  # pragma: no cover - exercised only without unstructured installed
    _default_partition = None

_SUPPORTED_SUFFIXES = frozenset(
    {'.txt', '.text', '.md', '.markdown', '.pdf', '.html', '.htm', '.docx'}
)


class UnstructuredParser(DocumentParser):
    """Parses documents via the `unstructured` library's auto-partitioner.

    Supports, at minimum, plain text, Markdown, PDF, HTML, and DOCX (DOCX
    requires the installed Unstructured configuration to include its `docx`
    extra). Elements are grouped by page number into one `Document` per page
    when the underlying format has pages (PDF, DOCX); formats without a page
    concept (txt, md, html) produce a single `Document`.
    """

    def __init__(
        self,
        *,
        strategy: str = 'fast',
        languages: Optional[Sequence[str]] = None,
        partition_fn: Optional[Callable[..., Any]] = None,
    ) -> None:
        """Initializes an UnstructuredParser.

        Args:
            strategy: Unstructured's partitioning strategy (e.g. `'fast'`,
                `'hi_res'`). Affects output, so it is part of this parser's
                config fingerprint.
            languages: Optional language hints passed through to Unstructured.
            partition_fn: A drop-in replacement for
                `unstructured.partition.auto.partition` -- bypasses the
                `unstructured` dependency check entirely, which is how tests
                exercise this class without it installed.

        Raises:
            OptionalDependencyError: Raised lazily, from `parse()`, if
                `unstructured` is not installed and no `partition_fn` was given
                (construction itself never requires the dependency).
        """
        self._partition = partition_fn or _default_partition
        self._strategy = strategy
        self._languages = tuple(languages) if languages else None

    @property
    def parser_type(self) -> str:
        return 'unstructured'

    def config(self) -> dict[str, Any]:
        return {'strategy': self._strategy, 'languages': self._languages}

    def parse(self, content: bytes, document: SourceDocument) -> list[Document]:
        if self._partition is None:
            raise OptionalDependencyError(
                package='unstructured', extra='rag-unstructured', feature='UnstructuredParser'
            )

        suffix = Path(document.name).suffix.lower()
        if suffix and suffix not in _SUPPORTED_SUFFIXES:
            raise UnsupportedDocumentError(
                f"UnstructuredParser does not support '{suffix}' files ({document.name!r})."
            )

        partition_kwargs: dict[str, Any] = {'strategy': self._strategy}
        if self._languages:
            partition_kwargs['languages'] = list(self._languages)
        if document.metadata.content_type:
            partition_kwargs['content_type'] = document.metadata.content_type

        try:
            elements = self._partition(
                file=io.BytesIO(content), metadata_filename=document.name, **partition_kwargs
            )
        except ImportError as exc:
            # A format-specific optional dependency (e.g. python-docx) is missing from
            # this installation -- distinct from a genuinely unsupported extension.
            raise UnsupportedDocumentError(
                f'{document.name!r} needs an Unstructured extra that is not installed: {exc}'
            ) from exc
        except Exception as exc:
            raise DocumentParseError(f'Failed to parse {document.name!r}: {exc}') from exc

        return _group_by_page(elements, document)


def _group_by_page(elements: Sequence[Any], document: SourceDocument) -> list[Document]:
    """Groups Unstructured elements sharing a page number into one Document each.

    Formats without pages (txt, md, html) leave every element's page_number
    unset, so they collapse into a single Document -- consistent with
    LangChain's own "paged" Unstructured loader mode.
    """
    pages: dict[Any, list[str]] = {}
    for element in elements:
        text = getattr(element, 'text', None) or str(element)
        if not text.strip():
            continue
        metadata = getattr(element, 'metadata', None)
        page_number = getattr(metadata, 'page_number', None)
        pages.setdefault(page_number, []).append(text)

    if not pages:
        return []

    return [
        Document(
            page_content='\n\n'.join(texts),
            metadata={
                'source_document_id': document.document_id,
                'filename': document.name,
                'page_number': page_number,
            },
        )
        for page_number, texts in pages.items()
    ]
