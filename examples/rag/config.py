# -*- coding: utf-8 -*-
# Copyright 2026 The Dapr Authors
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#     http://www.apache.org/licenses/LICENSE-2.0
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Shared, environment-variable-driven configuration for the RAG example scripts.

Every script in this directory (worker.py, cli.py, failure_demo.py, ...)
builds its `DurableRAGPipeline` through this module, so the same scripts work
across every supported source/embedder/vector-store combination -- see
`.env.example` for every variable, and `README.md` for the two worked
combinations from the SDK documentation (S3 + pgvector, Azure Blob +
Pinecone), plus the Azure-native flagship path (Azure Blob + Azure OpenAI +
Azure AI Search).
"""

from __future__ import annotations

import os
from typing import Optional

from dapr.ext.rag import (
    ActiveVersionResolver,
    AzureAISearchVectorStore,
    AzureBlobSource,
    AzureOpenAIEmbedder,
    DocumentSource,
    DurableRAGPipeline,
    Embedder,
    FoundryIQKnowledgeSourceConfig,
    OpenAIEmbedder,
    PgVectorStore,
    PineconeVectorStore,
    PipelineConfig,
    S3Source,
    TextSplitter,
    UnstructuredParser,
    VectorIndex,
)
from dapr.ext.rag.testing import FailureInjector


def require_env(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise SystemExit(f'Missing required environment variable: {name} (see .env.example)')
    return value


def optional_env(name: str) -> Optional[str]:
    return os.environ.get(name) or None


def build_source() -> DocumentSource:
    """Builds the configured `DocumentSource` from `RAG_SOURCE` ('s3' or 'azure-blob')."""
    provider = os.environ.get('RAG_SOURCE', 's3').lower()
    if provider == 's3':
        return S3Source(
            bucket=require_env('RAG_S3_BUCKET'),
            prefix=optional_env('RAG_S3_PREFIX'),
            region_name=optional_env('AWS_REGION'),
            # Set for LocalStack, e.g. http://localhost:4566 -- see README.md.
            endpoint_url=optional_env('RAG_S3_ENDPOINT_URL'),
        )
    if provider == 'azure-blob':
        return AzureBlobSource(
            account_url=optional_env('RAG_AZURE_ACCOUNT_URL'),
            container=require_env('RAG_AZURE_CONTAINER'),
            prefix=optional_env('RAG_AZURE_PREFIX'),
            # Set for Azurite or local dev; omit to use DefaultAzureCredential.
            connection_string=optional_env('RAG_AZURE_CONNECTION_STRING'),
        )
    raise SystemExit(f"Unknown RAG_SOURCE={provider!r}; expected 's3' or 'azure-blob'.")


def build_embedder() -> Embedder:
    """Builds the configured `Embedder` from `RAG_EMBEDDER` ('openai' or 'azure-openai')."""
    provider = os.environ.get('RAG_EMBEDDER', 'openai').lower()
    if provider == 'openai':
        return OpenAIEmbedder(
            model=os.environ.get('RAG_OPENAI_EMBEDDING_MODEL', 'text-embedding-3-small')
        )
    if provider == 'azure-openai':
        return AzureOpenAIEmbedder(
            endpoint=require_env('AZURE_OPENAI_ENDPOINT'),
            deployment=require_env('AZURE_OPENAI_EMBEDDING_DEPLOYMENT'),
            model=optional_env('AZURE_OPENAI_EMBEDDING_MODEL'),
            # Dev-only fallback; omit to use DefaultAzureCredential (recommended).
            api_key=optional_env('AZURE_OPENAI_API_KEY'),
        )
    raise SystemExit(f"Unknown RAG_EMBEDDER={provider!r}; expected 'openai' or 'azure-openai'.")


def build_vector_store() -> VectorIndex:
    """Builds the configured `VectorIndex` from `RAG_VECTOR_STORE`."""
    provider = os.environ.get('RAG_VECTOR_STORE', 'pgvector').lower()
    collection = os.environ.get('RAG_COLLECTION', 'company-knowledge')
    if provider == 'pgvector':
        return PgVectorStore(
            connection_string=require_env('RAG_PGVECTOR_CONNECTION_STRING'),
            collection=collection.replace('-', '_'),  # PgVectorStore requires a SQL-safe identifier
        )
    if provider == 'pinecone':
        return PineconeVectorStore(
            index_name=require_env('RAG_PINECONE_INDEX'), api_key=optional_env('PINECONE_API_KEY')
        )
    if provider == 'azure-ai-search':
        return AzureAISearchVectorStore(
            endpoint=require_env('AZURE_SEARCH_ENDPOINT'),
            index_base_name=collection,
            api_key=optional_env('AZURE_SEARCH_API_KEY'),
            semantic_configuration_name=optional_env('AZURE_SEARCH_SEMANTIC_CONFIG'),
        )
    raise SystemExit(
        f"Unknown RAG_VECTOR_STORE={provider!r}; expected 'pgvector', 'pinecone', or 'azure-ai-search'."
    )


def build_pipeline_id() -> str:
    """The pipeline ID every script agrees on, so the CLI/worker/query-time reader
    all address the same pipeline state without needing to construct a full
    `DurableRAGPipeline` (which requires source credentials) just to query it."""
    return os.environ.get('RAG_PIPELINE_ID') or os.environ.get(
        'RAG_COLLECTION', 'company-knowledge'
    )


def build_state_store_name() -> str:
    return os.environ.get('RAG_STATE_STORE', 'rag-pipeline-state')


def build_demo_failure_injector() -> Optional[FailureInjector]:
    """Builds a `FailureInjector` from `RAG_DEMO_FAIL_*` env vars, or `None`.

    See failure_demo.py and README.md's "Failure and resume demo" section --
    at most one of these should be set at a time, and never in a normal run.
    """
    if os.environ.get('RAG_DEMO_FAIL_AFTER_DOCUMENTS'):
        return FailureInjector(
            fail_after_documents=int(os.environ['RAG_DEMO_FAIL_AFTER_DOCUMENTS'])
        )
    if os.environ.get('RAG_DEMO_FAIL_AFTER_EMBEDDING_DOCUMENT'):
        return FailureInjector(
            fail_after_embedding_before_completion_for_document=os.environ[
                'RAG_DEMO_FAIL_AFTER_EMBEDDING_DOCUMENT'
            ]
        )
    if os.environ.get('RAG_DEMO_FAIL_DURING_BATCH'):
        return FailureInjector(
            fail_during_batch_index=int(os.environ['RAG_DEMO_FAIL_DURING_BATCH'])
        )
    return None


def build_foundry_iq_knowledge_source() -> Optional[FoundryIQKnowledgeSourceConfig]:
    """Builds a `FoundryIQKnowledgeSourceConfig` from `RAG_FOUNDRY_IQ_KNOWLEDGE_SOURCE`, or `None`.

    Opt-in and off by default -- see docs/rag/foundry-iq.md. Only meaningful with
    RAG_VECTOR_STORE=azure-ai-search; DurableRAGPipeline itself raises a clear ValueError at
    construction time if this is set alongside any other vector store.
    """
    name = optional_env('RAG_FOUNDRY_IQ_KNOWLEDGE_SOURCE')
    if not name:
        return None
    return FoundryIQKnowledgeSourceConfig(
        name=name,
        source_data_fields=tuple(_split_csv_env('RAG_FOUNDRY_IQ_SOURCE_DATA_FIELDS')),
        search_fields=tuple(_split_csv_env('RAG_FOUNDRY_IQ_SEARCH_FIELDS')),
    )


def _split_csv_env(name: str) -> list[str]:
    raw = optional_env(name)
    return [field.strip() for field in raw.split(',') if field.strip()] if raw else []


def build_pipeline(*, failure_injector: Optional[FailureInjector] = None) -> DurableRAGPipeline:
    """Builds the fully-configured `DurableRAGPipeline` for this environment."""
    return DurableRAGPipeline(
        source=build_source(),
        parser=UnstructuredParser(),
        splitter=TextSplitter(
            chunk_size=int(os.environ.get('RAG_CHUNK_SIZE', '1000')),
            chunk_overlap=int(os.environ.get('RAG_CHUNK_OVERLAP', '150')),
        ),
        embedder=build_embedder(),
        vector_store=build_vector_store(),
        state_store_name=build_state_store_name(),
        pipeline_id=build_pipeline_id(),
        config=PipelineConfig(
            max_concurrent_documents=int(os.environ.get('RAG_MAX_CONCURRENT_DOCUMENTS', '10')),
            embedding_batch_size=int(os.environ.get('RAG_EMBEDDING_BATCH_SIZE', '64')),
            fail_fast=os.environ.get('RAG_FAIL_FAST', 'false').lower() == 'true',
        ),
        pubsub_name=optional_env('RAG_ACTIVATION_PUBSUB'),
        foundry_iq_knowledge_source=build_foundry_iq_knowledge_source(),
        failure_injector=failure_injector or build_demo_failure_injector(),
    )


def build_retrieval_resolver() -> ActiveVersionResolver:
    """Builds a resolver for query-time use, without needing source credentials."""
    return ActiveVersionResolver(
        pipeline_id=build_pipeline_id(),
        state_store_name=build_state_store_name(),
        vector_store=build_vector_store(),
        embedder=build_embedder(),
    )
