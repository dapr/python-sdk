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
from typing import Any, Sequence

from dapr.ext.rag.fingerprints import compute_config_hash
from dapr.ext.rag.models import Chunk, Document

_DEFAULT_SEPARATORS: tuple[str, ...] = ('\n\n', '\n', ' ', '')


class DocumentSplitter(ABC):
    """Splits a parsed `Document` into ordered `Chunk`s."""

    @property
    @abstractmethod
    def splitter_type(self) -> str:
        """A short, stable name identifying this splitter for provenance."""

    @abstractmethod
    def split(self, document: Document) -> list[Chunk]:
        """Splits `document` into ordered chunks.

        Implementations must be deterministic: the same document must always
        produce the same chunk content in the same order, since chunk IDs are
        derived in part from `chunk_ordinal` and `chunk_content_hash`.
        """

    def config(self) -> dict[str, Any]:
        """Behavior-affecting configuration to fold into the splitter's fingerprint."""
        return {}

    def config_fingerprint(self) -> str:
        """A stable hash of `config()`, used to build the pipeline fingerprint."""
        return compute_config_hash(self.config())


class TextSplitter(DocumentSplitter):
    """A recursive character splitter with overlap (no third-party dependency).

    Recursively tries each separator in `separators` (paragraph, then line,
    then space, then a hard character cut) to break text into pieces no
    larger than `chunk_size`, then greedily merges adjacent pieces back up to
    `chunk_size`, carrying the trailing `chunk_overlap` characters of each
    chunk into the start of the next so context isn't lost at a chunk
    boundary.
    """

    def __init__(
        self,
        *,
        chunk_size: int = 1000,
        chunk_overlap: int = 150,
        separators: Sequence[str] = _DEFAULT_SEPARATORS,
    ) -> None:
        """Initializes a TextSplitter.

        Args:
            chunk_size: Maximum characters per chunk.
            chunk_overlap: Characters of context carried from the end of one
                chunk into the start of the next.
            separators: Tried in order to find split points; must end with
                `''` (or another separator guaranteed to appear) so recursion
                always terminates.

        Raises:
            ValueError: `chunk_size` isn't positive, or `chunk_overlap` isn't
                smaller than `chunk_size`.
        """
        if chunk_size < 1:
            raise ValueError('chunk_size must be >= 1')
        if chunk_overlap < 0:
            raise ValueError('chunk_overlap must be >= 0')
        if chunk_overlap >= chunk_size:
            raise ValueError('chunk_overlap must be smaller than chunk_size')
        self._chunk_size = chunk_size
        self._chunk_overlap = chunk_overlap
        self._separators = tuple(separators)

    @property
    def splitter_type(self) -> str:
        return 'text_splitter'

    def config(self) -> dict[str, Any]:
        return {
            'chunk_size': self._chunk_size,
            'chunk_overlap': self._chunk_overlap,
            'separators': list(self._separators),
        }

    def split(self, document: Document) -> list[Chunk]:
        pieces = _split_recursive(document.page_content, self._chunk_size, self._separators)
        merged = _merge_with_overlap(pieces, self._chunk_size, self._chunk_overlap)
        return [
            Chunk(chunk_ordinal=ordinal, content=text, metadata=dict(document.metadata))
            for ordinal, text in enumerate(merged)
            if text.strip()
        ]


def _split_recursive(text: str, chunk_size: int, separators: Sequence[str]) -> list[str]:
    if len(text) <= chunk_size or not separators:
        return [text] if text else []

    separator, *remaining = separators
    if separator == '':
        return [text[i : i + chunk_size] for i in range(0, len(text), chunk_size)]
    if separator not in text:
        return _split_recursive(text, chunk_size, remaining)

    pieces: list[str] = []
    parts = text.split(separator)
    for index, part in enumerate(parts):
        # Re-attach the separator to every part but the last, so re-joining
        # `pieces` losslessly reproduces the original text.
        piece = part + separator if index < len(parts) - 1 else part
        if not piece:
            continue
        if len(piece) > chunk_size:
            pieces.extend(_split_recursive(piece, chunk_size, remaining))
        else:
            pieces.append(piece)
    return pieces


def _merge_with_overlap(pieces: Sequence[str], chunk_size: int, chunk_overlap: int) -> list[str]:
    # A chunk's hard maximum length is chunk_size + chunk_overlap, not chunk_size:
    # after closing a chunk, the overlap tail (<= chunk_overlap chars) is
    # unconditionally joined with the next piece (<= chunk_size chars) before the
    # overflow check runs again, so that one join can exceed chunk_size by up to
    # chunk_overlap chars. It can't compound further: the very next piece added to
    # an already-oversized `current` immediately re-triggers the close, so no chunk
    # ever grows past chunk_size + chunk_overlap.
    chunks: list[str] = []
    current = ''
    for piece in pieces:
        if current and len(current) + len(piece) > chunk_size:
            chunks.append(current)
            # `current[-0:]` would be the *whole* string, not '' -- guard chunk_overlap == 0.
            current = current[-chunk_overlap:] if chunk_overlap else ''
        current += piece
    if current:
        chunks.append(current)
    return chunks
