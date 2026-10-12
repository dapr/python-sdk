# dapr.ext.rag

Durable RAG (retrieval-augmented generation) document ingestion on Dapr Workflow.
`DurableRAGPipeline` discovers documents from S3 or Azure Blob Storage, parses and chunks them,
generates embeddings, and writes them into a versioned pgvector or Pinecone index -- surviving
throttling, process crashes, and pod restarts by resuming from completed work.

```sh
pip install "dapr[rag,rag-s3,rag-pgvector]"      # S3 + pgvector
pip install "dapr[rag,rag-azure,rag-pinecone]"   # Azure Blob + Pinecone
```

```python
from dapr.ext.rag import DurableRAGPipeline, S3Source, UnstructuredParser, TextSplitter, OpenAIEmbedder, PgVectorStore

pipeline = DurableRAGPipeline(
    source=S3Source(bucket='company-docs', prefix='policies/'),
    parser=UnstructuredParser(),
    splitter=TextSplitter(chunk_size=1000, chunk_overlap=150),
    embedder=OpenAIEmbedder(model='text-embedding-3-small'),
    vector_store=PgVectorStore(connection_string='...', collection='company-knowledge'),
    state_store_name='rag-pipeline-state',
)
instance_id = pipeline.start(version='2026-09', activate_when_complete=True)
```

See [`AGENTS.md`](AGENTS.md) for architecture and internals, [`examples/rag/`](../../../examples/rag)
for a runnable worker/CLI/failure-demo, and [`docs/rag/README.md`](../../../docs/rag/README.md)
for full configuration, authentication, and operational documentation.
