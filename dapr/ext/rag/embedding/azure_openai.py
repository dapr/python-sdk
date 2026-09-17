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
from dapr.ext.rag.models import EmbeddingBatchResult

# Azure OpenAI additionally treats 408 (request timeout) as transient, on top
# of the 429/5xx every OpenAI-compatible endpoint shares.
_AZURE_EXTRA_TRANSIENT_STATUS_CODES = frozenset({408})


class AzureOpenAIEmbedder(Embedder):
    """Generates embeddings via an Azure OpenAI embeddings deployment.

    `deployment` (the customer-chosen name a request is actually routed by)
    and `model` (the underlying model the deployment runs, e.g.
    `text-embedding-3-small`) are tracked separately: Azure OpenAI requests
    are addressed by deployment name, but provenance and the pipeline
    fingerprint care about the model identity, and an operator renaming or
    repointing a deployment is exactly the kind of thing that should stay
    visible in provenance.
    """

    def __init__(
        self,
        *,
        endpoint: str,
        deployment: str,
        model: Optional[str] = None,
        api_version: str = _openai_common.DEFAULT_AZURE_API_VERSION,
        credential: Optional[Any] = None,
        api_key: Optional[str] = None,
        dimensions: Optional[int] = None,
        timeout: float = 60.0,
        client: Optional[Any] = None,
    ) -> None:
        """Initializes an AzureOpenAIEmbedder.

        Args:
            endpoint: The Azure OpenAI resource endpoint, e.g.
                `https://my-resource.openai.azure.com`.
            deployment: The embeddings deployment name to call.
            model: The underlying model name, for provenance and the
                pipeline fingerprint. Defaults to `deployment` when the
                deployment is named after its model (the common case); set
                this explicitly when it isn't.
            api_version: The Azure OpenAI REST API version.
            credential: An `azure-identity` credential for Microsoft Entra ID
                authentication. Defaults to `DefaultAzureCredential()`
                (managed identity, workload identity, `az login`, ...) when
                neither this nor `api_key` is given.
            api_key: Optional API key, for development only -- prefer
                `credential`/`DefaultAzureCredential` in production. Never
                logged or included in provenance/config fingerprints.
            dimensions: Optional reduced embedding dimensionality, for models
                that support it.
            timeout: Per-request timeout, in seconds.
            client: A pre-built `openai.AzureOpenAI` client (or any object
                exposing `.embeddings.create(...)`) to use instead of
                constructing one -- bypasses both the `openai` and
                `azure-identity` dependency checks, which is how tests
                exercise this class without either installed.

        Raises:
            OptionalDependencyError: A required package (`openai`, or
                `azure-identity` when using the default credential) is not
                installed and no `client` was given.
        """
        self._deployment = deployment
        self._model = model or deployment
        self._dimensions = dimensions
        self._client = client or _openai_common.build_azure_client(
            endpoint=endpoint,
            api_version=api_version,
            credential=credential,
            api_key=api_key,
            timeout=timeout,
            feature='AzureOpenAIEmbedder',
        )

    @property
    def embedding_model(self) -> str:
        return self._model

    @property
    def deployment(self) -> str:
        """The Azure OpenAI deployment name requests are routed to."""
        return self._deployment

    def config(self) -> dict[str, Any]:
        return {
            'deployment': self._deployment,
            'model': self._model,
            'dimensions': self._dimensions,
        }

    def embed_batch(self, texts: Sequence[str]) -> EmbeddingBatchResult:
        if not texts:
            return EmbeddingBatchResult(embeddings=[], total_tokens=0)

        # Azure OpenAI addresses a request by deployment name, in the `model` field.
        create_kwargs: dict[str, Any] = {'model': self._deployment, 'input': list(texts)}
        if self._dimensions is not None:
            create_kwargs['dimensions'] = self._dimensions

        try:
            response = self._client.embeddings.create(**create_kwargs)
        except Exception as exc:
            raise _openai_common.classify_error(
                exc, extra_transient_status_codes=_AZURE_EXTRA_TRANSIENT_STATUS_CODES
            ) from exc

        return _openai_common.parse_embeddings_response(response)
