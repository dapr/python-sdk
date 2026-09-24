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

# Unlike dapr.ext.langgraph/strands (each wrapping exactly one all-or-nothing
# third-party SDK, guarded by a single try/except here in __init__.py), this
# extension bundles several *independent* optional adapters (boto3,
# azure-storage-blob, azure-identity, azure-search-documents, openai, psycopg,
# pinecone, unstructured, langchain-core). Guarding the import here would mean
# the first missing package breaks `import dapr.ext.rag` entirely, even for
# users who only need e.g. pgvector. So each adapter module guards its own
# third-party import instead (see AGENTS.md), and raises
# OptionalDependencyError lazily, from the adapter class's constructor rather
# than at import time -- every import below is therefore unconditional and
# always succeeds.

from dapr.ext.rag.embedding import Embedder, OpenAIEmbedder
from dapr.ext.rag.embedding.azure_openai import AzureOpenAIEmbedder
from dapr.ext.rag.errors import (
    ActivationConflictError,
    DocumentChangedError,
    DocumentParseError,
    InvalidEmbeddingRequestError,
    InvalidGenerationRequestError,
    NonRetryableError,
    OptionalDependencyError,
    RagError,
    RetryableError,
    SourceAccessDeniedError,
    SourceNotFoundError,
    TransientEmbeddingError,
    TransientGenerationError,
    TransientSourceError,
    TransientVectorStoreError,
    UnsupportedDocumentError,
    VectorStoreError,
    VersionValidationError,
)
from dapr.ext.rag.fingerprints import (
    compute_chunk_id,
    compute_config_hash,
    compute_content_hash,
    compute_manifest_hash,
    compute_pipeline_fingerprint,
)
from dapr.ext.rag.generation import AzureOpenAIChatClient
from dapr.ext.rag.models import (
    ActivationRecord,
    AnswerResult,
    Chunk,
    Citation,
    CompletionRecord,
    Document,
    DocumentFailure,
    DocumentOutcome,
    DocumentOutcomeStatus,
    DocumentWorkItem,
    EmbeddingBatchResult,
    EmbedProgressRecord,
    FoundryIQKnowledgeSourceConfig,
    ManifestSummary,
    PipelineConfig,
    PipelineStage,
    PipelineStatus,
    ProvenanceRecord,
    QueryMatch,
    SourceChangeEvent,
    SourceDocument,
    SourceMetadata,
    SourceProvider,
    UpsertResult,
    ValidationResult,
    VectorRecord,
)
from dapr.ext.rag.parsing import (
    DocumentParser,
    UnstructuredParser,
    from_langchain_documents,
    to_langchain_documents,
)
from dapr.ext.rag.pipeline import DurableRAGPipeline
from dapr.ext.rag.retrieval import ActiveVersionResolver
from dapr.ext.rag.sources import AzureBlobSource, DocumentSource, S3Source
from dapr.ext.rag.splitting import DocumentSplitter, TextSplitter
from dapr.ext.rag.state import PipelineStateStore
from dapr.ext.rag.testing import FailureInjector
from dapr.ext.rag.triggers import (
    EventDeduplicator,
    StorageEventNotification,
    parse_azure_blob_event,
    parse_s3_event_notifications,
    to_source_change_event,
)
from dapr.ext.rag.vector_stores import (
    AzureAISearchVectorStore,
    PgVectorStore,
    PineconeVectorStore,
    VectorIndex,
)

__all__ = [
    # Pipeline
    'DurableRAGPipeline',
    'PipelineConfig',
    'PipelineStatus',
    'PipelineStage',
    'PipelineStateStore',
    'FoundryIQKnowledgeSourceConfig',
    # Retrieval
    'ActiveVersionResolver',
    # Generation (query-time; not part of the durable ingestion path)
    'AzureOpenAIChatClient',
    'AnswerResult',
    'Citation',
    # Sources
    'DocumentSource',
    'S3Source',
    'AzureBlobSource',
    # Parsing
    'DocumentParser',
    'UnstructuredParser',
    'to_langchain_documents',
    'from_langchain_documents',
    # Splitting
    'DocumentSplitter',
    'TextSplitter',
    # Embedding
    'Embedder',
    'OpenAIEmbedder',
    'AzureOpenAIEmbedder',
    'EmbeddingBatchResult',
    # Vector stores
    'VectorIndex',
    'PgVectorStore',
    'PineconeVectorStore',
    'AzureAISearchVectorStore',
    'QueryMatch',
    # Models
    'SourceDocument',
    'SourceMetadata',
    'SourceProvider',
    'DocumentWorkItem',
    'Document',
    'Chunk',
    'VectorRecord',
    'UpsertResult',
    'ValidationResult',
    'ActivationRecord',
    'ProvenanceRecord',
    'DocumentOutcome',
    'DocumentOutcomeStatus',
    'DocumentFailure',
    'ManifestSummary',
    'CompletionRecord',
    'EmbedProgressRecord',
    # Fingerprints
    'compute_chunk_id',
    'compute_config_hash',
    'compute_content_hash',
    'compute_manifest_hash',
    'compute_pipeline_fingerprint',
    # Triggers
    'SourceChangeEvent',
    'StorageEventNotification',
    'parse_s3_event_notifications',
    'parse_azure_blob_event',
    'to_source_change_event',
    'EventDeduplicator',
    # Testing
    'FailureInjector',
    # Errors
    'RagError',
    'OptionalDependencyError',
    'RetryableError',
    'NonRetryableError',
    'TransientSourceError',
    'SourceNotFoundError',
    'SourceAccessDeniedError',
    'DocumentChangedError',
    'UnsupportedDocumentError',
    'DocumentParseError',
    'TransientEmbeddingError',
    'InvalidEmbeddingRequestError',
    'TransientGenerationError',
    'InvalidGenerationRequestError',
    'TransientVectorStoreError',
    'VectorStoreError',
    'VersionValidationError',
    'ActivationConflictError',
]
