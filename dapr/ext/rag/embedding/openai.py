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

from typing import Any, Optional, Sequence

from dapr.ext.rag.embedding import _openai_common
from dapr.ext.rag.embedding.base import Embedder
from dapr.ext.rag.errors import OptionalDependencyError
from dapr.ext.rag.models import EmbeddingBatchResult

# See dapr/ext/rag/AGENTS.md for why the optional-dependency guard lives here,
# per adapter module, rather than once in dapr/ext/rag/__init__.py.
try:
    import openai
except ImportError:  # pragma: no cover - exercised only without openai installed
    openai = None  # type: ignore[assignment]


class OpenAIEmbedder(Embedder):
    """Generates embeddings via the OpenAI embeddings API."""

    def __init__(
        self,
        *,
        model: str = 'text-embedding-3-small',
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        dimensions: Optional[int] = None,
        timeout: float = 60.0,
        client: Optional[Any] = None,
    ) -> None:
        """Initializes an OpenAIEmbedder.

        Args:
            model: The embedding model to use.
            api_key: Optional explicit API key; otherwise resolved by the
                `openai` client from the `OPENAI_API_KEY` environment
                variable. Never logged or included in provenance/config
                fingerprints.
            base_url: Optional API base URL override (e.g. for an
                OpenAI-compatible gateway).
            dimensions: Optional reduced embedding dimensionality, for models
                that support it.
            timeout: Per-request timeout, in seconds.
            client: A pre-built `openai.OpenAI` client (or any object
                exposing `.embeddings.create(...)`) to use instead of
                constructing one -- bypasses the `openai` dependency check
                entirely, which is how tests exercise this class without it
                installed.

        Raises:
            OptionalDependencyError: `openai` is not installed and no
                `client` was given.
        """
        self._model = model
        self._dimensions = dimensions

        if client is not None:
            self._client = client
        else:
            if openai is None:
                raise OptionalDependencyError(
                    package='openai', extra='rag', feature='OpenAIEmbedder'
                )
            client_kwargs: dict[str, Any] = {'timeout': timeout}
            if api_key is not None:
                client_kwargs['api_key'] = api_key
            if base_url is not None:
                client_kwargs['base_url'] = base_url
            self._client = openai.OpenAI(**client_kwargs)

    @property
    def embedding_model(self) -> str:
        return self._model

    def config(self) -> dict[str, Any]:
        return {'model': self._model, 'dimensions': self._dimensions}

    def embed_batch(self, texts: Sequence[str]) -> EmbeddingBatchResult:
        if not texts:
            return EmbeddingBatchResult(embeddings=[], total_tokens=0)

        create_kwargs: dict[str, Any] = {'model': self._model, 'input': list(texts)}
        if self._dimensions is not None:
            create_kwargs['dimensions'] = self._dimensions

        try:
            response = self._client.embeddings.create(**create_kwargs)
        except Exception as exc:
            raise _openai_common.classify_error(exc) from exc

        return _openai_common.parse_embeddings_response(response)
