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

from typing import Any, Optional

from dapr.clients import DaprClient
from dapr.ext.rag.embedding.base import Embedder
from dapr.ext.rag.errors import VersionValidationError
from dapr.ext.rag.models import QueryMatch
from dapr.ext.rag.state import PipelineStateStore
from dapr.ext.rag.vector_stores.base import VectorIndex


class ActiveVersionResolver:
    """Resolves a pipeline's active version and queries only that version.

    This is deliberately independent of `DurableRAGPipeline` and the
    workflow runtime: any reader process (a retrieval service, a notebook, a
    CLI) can construct one directly to query the currently-active index while
    a new version is being built in the background, without ever seeing a
    partially-built version. Not a workflow activity -- ordinary client-side
    code, exactly like `DaprWorkflowClient.get_workflow_state()`.
    """

    def __init__(
        self,
        *,
        pipeline_id: str,
        state_store_name: str,
        vector_store: VectorIndex,
        embedder: Embedder,
        dapr_client: Optional[DaprClient] = None,
    ) -> None:
        """Initializes an ActiveVersionResolver.

        Args:
            pipeline_id: The pipeline whose active version to resolve.
            state_store_name: The Dapr state store holding the activation record.
            vector_store: The `VectorIndex` to query once a version is resolved.
            embedder: Used to embed query text with the same model used at
                ingestion time.
            dapr_client: A `DaprClient` to reuse; a new one is created (and
                owned/closed by this instance) when omitted.
        """
        self._vector_store = vector_store
        self._embedder = embedder
        self._state = PipelineStateStore(state_store_name=state_store_name, dapr_client=dapr_client)
        self._pipeline_id = pipeline_id

    def resolve_active_version(self) -> Optional[str]:
        """Returns the pipeline's currently-active version, or `None` if never activated."""
        record, _etag = self._state.read_activation(self._pipeline_id)
        return record.active_version if record is not None else None

    def query(
        self,
        text: str,
        *,
        top_k: int = 5,
        metadata_filter: Optional[dict[str, Any]] = None,
    ) -> list[QueryMatch]:
        """Embeds `text` and searches only the currently-active version.

        Raises:
            VersionValidationError: No version has ever been activated for
                this pipeline.
        """
        version = self.resolve_active_version()
        if version is None:
            raise VersionValidationError(
                f'Pipeline {self._pipeline_id!r} has no active version yet.'
            )
        result = self._embedder.embed_batch([text])
        return self._vector_store.query(
            result.embeddings[0],
            version,
            top_k=top_k,
            metadata_filter=metadata_filter,
            query_text=text,
        )

    def close(self) -> None:
        """Releases the underlying `DaprClient`, if this instance created it."""
        self._state.close()
