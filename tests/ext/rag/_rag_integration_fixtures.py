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

# Shared between test_pipeline_integration.py (in-process) and _crash_resume_worker.py (a
# separate subprocess) -- both need the *exact same* Embedder/DocumentParser classes so a
# document embedded by one process and re-checked by the other agree on content hashes and
# embeddings. No test_ prefix (not collected by pytest itself); no leading underscore would
# make this look like a test module too, hence the _ prefix instead.

from __future__ import annotations

import hashlib
from typing import Sequence

from dapr.ext.rag.embedding.base import Embedder
from dapr.ext.rag.errors import UnsupportedDocumentError
from dapr.ext.rag.models import Document, EmbeddingBatchResult, SourceDocument
from dapr.ext.rag.parsing.base import DocumentParser


class DeterministicEmbedder(Embedder):
    """A hash-based, fully offline stand-in for a real embedding provider.

    Deterministic (same text -> same vector always, including across separate process runs) so
    a re-run of unchanged content is a genuine test of the pipeline's own idempotency, not an
    artifact of embedding randomness. Uses `hashlib.sha256`, not the builtin `hash()`, which is
    salted per-process (see `fingerprints.py` for the same rule applied to production code).
    """

    _DIMENSIONS = 8

    @property
    def embedding_model(self) -> str:
        return 'deterministic-test-embedder-v1'

    def embed_batch(self, texts: Sequence[str]) -> EmbeddingBatchResult:
        embeddings = [self._embed_one(text) for text in texts]
        return EmbeddingBatchResult(embeddings=embeddings, total_tokens=sum(len(t) for t in texts))

    def _embed_one(self, text: str) -> list[float]:
        digest = hashlib.sha256(text.encode('utf-8')).digest()
        return [byte / 255.0 for byte in digest[: self._DIMENSIONS]]


class PlainTextParser(DocumentParser):
    """Decodes bytes as UTF-8 text, one `Document` per file -- no `unstructured` dependency.

    Real format detection (PDF/DOCX/HTML/...) is already covered by
    `test_parsing_unstructured.py` against a mocked `partition()`; these integration tests'
    job is proving the *workflow* is durable, not proving parsing correctness a second time.
    """

    @property
    def parser_type(self) -> str:
        return 'plain-text-test-parser'

    def parse(self, content: bytes, document: SourceDocument) -> list[Document]:
        if not document.name.endswith('.txt'):
            raise UnsupportedDocumentError(
                f'Only .txt is supported by this test parser: {document.name}'
            )
        return [Document(page_content=content.decode('utf-8'), metadata={})]
