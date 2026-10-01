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
from dapr.ext.rag.models import EmbeddingBatchResult


class Embedder(ABC):
    """Generates embeddings for chunk text, in caller-controlled batches.

    Implementations perform network I/O and must only ever be called from
    within a workflow activity, never from the orchestrator.
    """

    @property
    @abstractmethod
    def embedding_model(self) -> str:
        """The specific model name used, for provenance (e.g. 'text-embedding-3-small')."""

    @abstractmethod
    def embed_batch(self, texts: Sequence[str]) -> EmbeddingBatchResult:
        """Embeds a batch of texts, preserving input order in the result.

        Args:
            texts: Chunk texts to embed. Callers are responsible for keeping
                batches within the provider's request limits (see
                `PipelineConfig.embedding_batch_size`).

        Returns:
            An `EmbeddingBatchResult` with one embedding per input text, in
            the same order, plus token usage when the provider reports it.

        Raises:
            TransientEmbeddingError: The request failed transiently
                (throttling, timeout, provider-side 5xx).
            InvalidEmbeddingRequestError: The provider rejected the request
                as invalid; retrying it unchanged will not help.
        """

    def config(self) -> dict[str, Any]:
        """Behavior-affecting configuration to fold into this embedder's fingerprint.

        Must be JSON-serializable and must not include secrets (API keys).
        """
        return {'model': self.embedding_model}

    def config_fingerprint(self) -> str:
        """A stable hash of `config()`, used to build the pipeline fingerprint."""
        return compute_config_hash(self.config())
