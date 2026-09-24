# Alternative architecture: Azure AI Search integrated vectorization

This is a short note on a legitimate alternative to this pipeline's architecture, for anyone
evaluating whether they need `DurableRAGPipeline` at all: Azure AI Search **indexers with
integrated vectorization** (skillsets that chunk and embed documents as part of indexing), where
Search itself owns ingestion end to end. This is a design note, not shipped code: `dapr.ext.rag`
does not include a class for this, and deliberately so -- see "Why `DurableRAGPipeline`
deliberately does not use it" below. An earlier version of this package briefly shipped one
(`AzureSearchIntegratedVectorizationPipeline`) and removed it: that class had no Dapr Workflow,
Dapr client, or Dapr sidecar involvement whatsoever, and packaging plain `azure-search-documents`
SDK orchestration inside a Dapr extension risked implying it inherited `DurableRAGPipeline`'s
durability guarantees, which it fundamentally cannot (an indexer run's own retry/recovery
behavior is opaque to the caller -- see reason 1 below). If you want this architecture, build it
directly against `azure-search-documents` in your own application code, outside this package.

## What integrated vectorization is

An Azure AI Search **indexer** can read documents directly from a source (including Blob Storage)
and run a **skillset** against each one as part of indexing -- built-in or custom skills that
split text into chunks and call an embedding model (including an Azure OpenAI embeddings
deployment) inline, writing the resulting text and vector fields straight into the index. Search
manages the crawl/re-crawl schedule, change detection, and the chunk-and-embed step itself. For a
single Azure-AI-Search-only deployment with a straightforward document set, this is a
legitimate, lower-code way to get from "documents in Blob Storage" to "a queryable vector index" --
no separate compute layer, orchestrator, or workflow engine required.

## Why this pipeline deliberately does not use it

`DurableRAGPipeline` keeps ingestion, retries, and checkpointing inside Dapr Workflow instead, for
four reasons specific to what this sample is trying to guarantee:

1. **Durability across worker crashes and pod restarts.** An indexer run is a black box from the
   caller's perspective: if it fails partway through a large corpus, the recovery story is
   "re-run the indexer" (or rely on its own internal, less transparent retry/resume behavior), not
   "resume exactly the documents that were not yet durably processed." Dapr Workflow's durable
   execution means killing and restarting the worker process mid-run resumes from the last
   completed activity, not from scratch -- with no application code needed for the crash-recovery
   half of that guarantee (see `dapr/ext/rag/AGENTS.md`'s "Idempotency and recovery" section).
2. **Avoided recomputation via idempotent per-document/per-batch state.** Because this pipeline
   tracks completion at the document and embedding-batch level (content-hash-keyed
   `CompletionRecord`/`EmbedProgressRecord`s in the state store), re-processing a version after a
   prior failed attempt skips everything already durably completed -- including embeddings, which
   are the expensive, rate-limited, billed part of ingestion. An indexer re-run's unit of
   "already done" is coarser and less exposed to the caller.
3. **Provenance recorded per chunk.** Every vector this pipeline writes carries a full
   `ProvenanceRecord` in its metadata (pipeline/workflow IDs, source identity, content/config
   hashes, parser/splitter/embedder identity, target index/version, timestamp, attempt number) --
   queryable alongside search results, and exactly what makes the correlation narrative in
   `docs/rag/observability.md` possible. An indexer-driven pipeline can populate custom metadata
   fields too, but that provenance has to be designed and maintained as part of the skillset
   rather than coming from a workflow engine that already tracks this state for its own recovery
   purposes.
4. **One ingestion model across deployment targets.** Integrated vectorization is Azure AI
   Search-specific -- it has no equivalent for this same pipeline's S3 + pgvector/Pinecone
   deployment target, which has no "indexer" concept at all. Because `DurableRAGPipeline`'s
   ingestion logic (discover, download, parse, chunk, embed, upsert, validate, activate) lives in
   Dapr Workflow activities calling pluggable `DocumentSource`/`DocumentParser`/`Embedder`/
   `VectorIndex` adapters, the *same* orchestration code and the *same* durability/idempotency
   guarantees apply whether the target is Azure Blob Storage + Azure AI Search or S3 + pgvector/
   Pinecone. Integrated vectorization would only ever cover the former, meaning a team supporting
   both targets would need two entirely different ingestion architectures.

## When integrated vectorization is the better choice

If your deployment is Azure-AI-Search-only, your corpus is modest, you do not need cross-restart
durability guarantees stronger than "re-run the indexer," and you would rather not run a workflow
worker process at all, integrated vectorization is a reasonable, simpler starting point. The two
approaches are not mutually exclusive within Azure AI Search itself -- but mixing them against the
*same* index (part indexer-managed, part Dapr-Workflow-managed) is not a configuration this sample
supports or recommends: pick one system as the owner of a given index's ingestion.
