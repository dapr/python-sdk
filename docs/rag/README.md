# Durable RAG ingestion (`dapr.ext.rag`)

`DurableRAGPipeline` durably ingests documents from a cloud object store into a versioned vector
index, using Dapr Workflow for orchestration. See [`dapr/ext/rag/AGENTS.md`](../../dapr/ext/rag/AGENTS.md)
for the internal architecture reference (module layout, why each design choice was made); this
document is the user-facing guide: the problem, configuration for every supported provider,
authentication, operations, and the Azure-native flagship path.

## The problem this solves

Indexing a large document corpus for retrieval-augmented generation means downloading, parsing,
chunking, and embedding potentially thousands of documents, then writing the result into a vector
index -- a process that can run for hours and is exposed to exactly the failures long-running jobs
always are: the embedding provider throttles you, a network call times out, the worker process
gets OOM-killed or the pod is rescheduled mid-run. A naive batch script either loses all progress on
a crash (reprocessing, and re-paying for, every document) or -- worse -- partially updates a *live*
index that queries are already reading from, serving incomplete results while ingestion is still
running.

`DurableRAGPipeline` addresses both problems structurally: Dapr Workflow durably checkpoints
progress at the activity level, so a crash resumes from the last completed step rather than the
beginning; and every ingestion run builds a separate, inactive index version, which is only ever
switched to "active" after it validates as complete -- so a query never sees a partially-built
index.

## Architecture and durability boundaries

```mermaid
flowchart TD
    subgraph Orchestrator["rag_ingest orchestrator (deterministic)"]
        A[discover_and_manifest] --> B[get_manifest_batch]
        B --> C["process_document x N (bounded batch)"]
        C --> D[update_status]
        D -->|more batches| B
        D -->|done| E[validate_version]
        E -->|valid| F[activate_version]
        F --> G[publish_activation_event]
    end
    C -->|I/O| Source[(DocumentSource\nS3 / Azure Blob)]
    C -->|I/O| Parser[DocumentParser + DocumentSplitter]
    C -->|I/O| Embedder[(Embedder\nOpenAI / Azure OpenAI)]
    C -->|I/O| Store[(VectorIndex\npgvector / Pinecone / Azure AI Search)]
    A -->|I/O| Source
    E -->|I/O| Store
    F -->|I/O| Store
    C -->|I/O| State[(Dapr state:\nmanifest, completion,\nembed progress)]
    F -->|I/O| Activation[(Dapr state:\nActivationRecord, ETag-guarded)]
    Reader[Reader process\nActiveVersionResolver] -->|resolves + queries| Activation
    Reader --> Store
```

**Why every external call is a workflow activity, never orchestrator code.** Dapr Workflow replays
an orchestrator function from its recorded history to resume after a crash -- that only produces
the same result on replay if the orchestrator is a pure function of its inputs and history (see
[`dapr/ext/workflow/AGENTS.md`](../../dapr/ext/workflow/AGENTS.md)'s determinism rules). Listing a
bucket, downloading a blob, calling an embedding API, writing a vector, reading or writing Dapr
state, and generating a timestamp are all either I/O or non-deterministic -- every one of them runs
inside a `pipeline.py` `_activity_*` method, never in `_orchestrate_ingestion` itself, which only
ever calls `ctx.call_activity(...)`, reads `ctx.current_utc_datetime`, and does plain
in-memory bookkeeping on its own (flat, replay-safe) input state.

## Supported combinations

| Concern | Options |
|---|---|
| Source | `S3Source`, `AzureBlobSource` |
| Parser | `UnstructuredParser` (txt, md, PDF, HTML, DOCX) |
| Splitter | `TextSplitter` |
| Embedder | `OpenAIEmbedder`, `AzureOpenAIEmbedder` |
| Vector store | `PgVectorStore`, `PineconeVectorStore`, `AzureAISearchVectorStore` |

Any source can pair with any embedder and any vector store -- see `examples/rag/config.py` for a
single set of scripts that switches between all of them via environment variables.

## Configuration

### S3 (`S3Source`)

```python
from dapr.ext.rag import S3Source

source = S3Source(bucket="company-docs", prefix="policies/")
```

Credentials come from **boto3's standard credential-provider chain** (environment variables,
shared config/credentials files, an EC2/ECS/EKS instance or task role, SSO) -- nothing in this
class requires a static access key. Pass `endpoint_url="http://localhost:4566"` to target
LocalStack for local development (see below), and `region_name`/explicit
`aws_access_key_id`/`aws_secret_access_key` only where you genuinely need to override the chain
(LocalStack's fixed test credentials, for instance). Requires the `rag-s3` extra
(`pip install "dapr[rag,rag-s3]"`).

### Azure Blob Storage (`AzureBlobSource`)

```python
from dapr.ext.rag import AzureBlobSource

source = AzureBlobSource(account_url="https://example.blob.core.windows.net", container="company-docs", prefix="policies/")
```

Authenticates with **`DefaultAzureCredential`** by default (managed identity, workload identity,
`az login`, environment credentials, in that standard order) -- again, no static secret required.
Pass `connection_string=...` instead for Azurite or another local/dev connection string, or inject
`credential=` for any other `azure-identity` credential type. Requires the `rag-azure` extra
(`pip install "dapr[rag,rag-azure]"`).

### OpenAI embeddings (`OpenAIEmbedder`)

```python
from dapr.ext.rag import OpenAIEmbedder

embedder = OpenAIEmbedder(model="text-embedding-3-small")
```

Resolves `OPENAI_API_KEY` from the environment by default. Requires the `rag` extra
(`pip install "dapr[rag]"`).

### Azure OpenAI embeddings (`AzureOpenAIEmbedder`)

```python
from azure.identity import DefaultAzureCredential
from dapr.ext.rag import AzureOpenAIEmbedder

embedder = AzureOpenAIEmbedder(
    endpoint="https://my-resource.openai.azure.com",
    deployment="text-embedding-3-small",
    credential=DefaultAzureCredential(),  # this is also the default when omitted
)
```

`deployment` (what a request is actually routed by) and `model` (the underlying model, defaulted
from `deployment` when not given separately) are tracked independently and both recorded in
provenance -- an operator repointing a deployment to a different model version is exactly the kind
of change provenance should make visible. Authenticates via Microsoft Entra ID
(`DefaultAzureCredential` by default) using a bearer-token provider; `api_key=` is accepted for
local development only. Classifies HTTP 429/408/5xx as retryable and surfaces a `Retry-After`
header (as `retry_after_seconds` on the raised `TransientEmbeddingError`) when the service sends
one. Requires the `rag` and `rag-azure` extras.

### PostgreSQL + pgvector (`PgVectorStore`)

```python
from dapr.ext.rag import PgVectorStore

vector_store = PgVectorStore(connection_string="postgresql://user:password@host/db", collection="company_knowledge")
```

All versions of one `collection` share a single physical table (`rag_chunks_{collection}`), scoped
by a `version` column with a `(version, chunk_id)` primary key -- no separate database or table per
version, and no destructive changes to an existing table (schema is created with `CREATE TABLE IF
NOT EXISTS` on first use). `collection` must be a safe SQL identifier (letters, digits,
underscores). Requires the `rag-pgvector` extra (`psycopg[binary]`).

### Pinecone (`PineconeVectorStore`)

```python
from dapr.ext.rag import PineconeVectorStore

vector_store = PineconeVectorStore(index_name="company-knowledge")
```

Uses one **namespace per version** within a single Pinecone index (create the index itself, with a
matching vector dimension/metric, ahead of time -- this class does not create indexes). Resolves
`PINECONE_API_KEY` from the environment by default. Requires the `rag-pinecone` extra.

### Azure AI Search (`AzureAISearchVectorStore`) -- the Azure-native flagship path

```python
from dapr.ext.rag import AzureAISearchVectorStore

vector_store = AzureAISearchVectorStore(
    endpoint="https://my-search.search.windows.net",
    index_base_name="company-knowledge",   # creates company-knowledge-{version} indexes
    semantic_configuration_name="company-knowledge-semantic",  # optional
)
```

Unlike pgvector/Pinecone, a version here is a **whole separate physical index**
(`{index_base_name}-{version}`), not a column/namespace inside one always-queryable index -- see
[Version activation](#version-activation) below for why that changes how activation works.
Authenticates via `DefaultAzureCredential` by default (`api_key=` for local development). Supports
vector-only, keyword-only, and hybrid (default) retrieval, with optional semantic ranking; the
`content_vector` field is never returned from a query unless you explicitly ask for it
(`include_vector=True`). Batch upserts inspect Azure AI Search's per-document indexing result and
retry only the documents that failed, not the whole batch. Requires the `rag-azure-search` extra
(`azure-search-documents`).

## Authentication summary

| Provider | Default | Local/dev override |
|---|---|---|
| AWS (S3) | Default credential provider chain (env, shared config, instance/task role, SSO) | Explicit `aws_access_key_id`/`aws_secret_access_key`, or `endpoint_url` for LocalStack |
| Azure (Blob, OpenAI, AI Search) | `DefaultAzureCredential` (managed/workload identity, `az login`, ...) | `connection_string` (Blob/Azurite) or `api_key` (OpenAI/AI Search) |

No adapter in this package requires a static credential in code or configuration for its
recommended path. See [`docs/rag/azure-rbac.md`](azure-rbac.md) for the exact Azure role
assignments the Azure-native deployment needs, split between an ingestion identity (index/document
write, alias switch) and a query identity (read-only) -- the query identity must never be able to
write documents, create indexes, or switch the alias.

## Starting, observing, and querying a pipeline

```python
pipeline = DurableRAGPipeline(
    source=..., parser=UnstructuredParser(), splitter=TextSplitter(chunk_size=1000, chunk_overlap=150),
    embedder=..., vector_store=..., state_store_name="rag-pipeline-state",
)
pipeline.run_worker()  # only in the process that should execute the workflow -- see examples/rag/worker.py

instance_id = pipeline.start(version="2026-09", activate_when_complete=True)
status = pipeline.get_status("2026-09")     # PipelineStatus: counts, chunks, retries, bytes, stage, ...
active = pipeline.resolve_active_version()  # None until activation succeeds
```

A short-lived client process (a CLI, a script) never needs to call `run_worker()` -- constructing a
`DurableRAGPipeline` only registers activities locally and is safe without a live sidecar;
`start()`/`get_status()`/`resolve_active_version()` all just talk to Dapr through the sidecar. See
`examples/rag/cli.py` and `examples/rag/worker.py` for the worker/client split in practice, and
`examples/rag/README.md` for exact commands.

For query-time retrieval, use `ActiveVersionResolver` directly rather than constructing a full
pipeline (it needs only the vector store, embedder, and state store -- not source credentials):

```python
from dapr.ext.rag import ActiveVersionResolver

resolver = ActiveVersionResolver(pipeline_id="company-knowledge", state_store_name="rag-pipeline-state",
                                  vector_store=..., embedder=...)
matches = resolver.query("What is the remote work policy?", top_k=5)
```

`resolver.query(...)` always resolves the active version fresh (with strong read consistency) and
searches only that version -- a reader never needs its own logic to avoid an in-progress build.

## Version activation

An `ActivationRecord` (`pipeline_id`, `active_version`, `previous_version`, `manifest_hash`,
`activated_at`, `workflow_instance_id`) lives at a single Dapr state key per pipeline, updated only
via an ETag-conditional write -- a concurrent activation attempt gets Dapr's `ABORTED` status,
which surfaces as a retryable `ActivationConflictError` (the workflow's own retry re-reads the
current ETag, so no bespoke retry loop is needed). Activation only ever follows successful
`validate_version`, and repeated activation of the same `(version, manifest_hash)` is a no-op.

For pgvector and Pinecone, this record *is* the whole activation mechanism -- `version` is a
column/namespace inside one always-queryable index, so flipping the pointer is enough.
**Azure AI Search is different**: each version is a separate physical index, so an
`ActivationRecord` alone doesn't change what a query actually reads. `AzureAISearchVectorStore`
participates in a second step (`VectorIndex.activate_version`, called from the same activity,
before the Dapr-state write): it reads the current alias mapping, does nothing if it already points
at the target index (idempotent), otherwise atomically repoints the alias
(`{index_base_name}-active` by default) and polls until the change is observable -- never deleting
or repurposing the previous version's index. The query path should read through this alias, not a
version-specific index name; `examples/rag/query_api.py` does exactly that.

The alias switch itself is implemented as a direct call to the Search REST API, not the
`azure-search-documents` SDK: the SDK has no alias support at all (removed before its stable 11.4.0
release and never restored). See
[`dapr/ext/rag/AGENTS.md`](../../dapr/ext/rag/AGENTS.md#azure-ai-search-index-aliases-are-rest-only-not-sdk-only)
for the full finding -- it doesn't change any of the behavior described above, only how it talks to
Azure AI Search under the hood.

## Recovery and retry behavior

Two independent mechanisms make a crash recoverable, described in full (with the exact state-store
key schema) in [`dapr/ext/rag/AGENTS.md`](../../dapr/ext/rag/AGENTS.md#idempotency-and-recovery-the-core-value-proposition):

1. **Dapr Workflow's own crash recovery.** Orchestration state lives in the Dapr-managed backend,
   not the worker process's memory. Restarting the *same* worker process reconnects and resumes the
   same instance automatically -- see `examples/rag/README.md`'s failure demo for how to see this
   directly.
2. **Per-document idempotency in Dapr state**, for a brand-new workflow instance re-processing the
   same version (e.g. after a prior instance reached a terminal failed state). A completion record
   is written only *after* a document's vectors are durably upserted, and embedding progress is
   tracked per batch, so "crashed mid-embedding" never loses or duplicates more than one in-flight
   batch's worth of work.

Retryable failures (throttling, timeouts, transient 5xx) are retried by the workflow's own
`RetryPolicy` with exponential backoff (`PipelineConfig.first_retry_interval_seconds`/
`backoff_coefficient`/`max_retry_interval_seconds`/`max_activity_attempts`); non-retryable failures
(corrupt/unsupported documents, invalid embedding requests) are recorded as a failed document and
never retried, so no retry budget is wasted on something retrying can't fix.

## Provenance

Every indexed chunk's vector-store metadata carries a full `ProvenanceRecord`: pipeline and
workflow-instance IDs, source provider/document ID/URI/ETag/version/content type/content hash,
document and chunk ordinals, chunk content hash, parser and splitter type + config hash, embedding
provider/model/deployment, target index and version, ingestion timestamp, and activity attempt
number -- see `dapr/ext/rag/models.py`'s `ProvenanceRecord` for the exact fields. No credential,
signed URL, or connection string is ever included: adapter `config()` methods (which feed the
pipeline fingerprint and are safe to log) are hand-written to return only non-secret,
behavior-affecting settings.

## Local development with LocalStack and Azurite

```python
# S3 against LocalStack
S3Source(bucket="company-docs", endpoint_url="http://localhost:4566", aws_access_key_id="test", aws_secret_access_key="test")

# Azure Blob against Azurite
AzureBlobSource(container="company-docs", connection_string="UseDevelopmentStorage=true")
```

Both accept an injected `client=`, so the default unit test run exercises the same adapter code
against a fake without either service installed -- see `tests/ext/rag/test_sources_s3.py` and
`test_sources_azure_blob.py`. There is also a real, opt-in integration profile that runs against
live LocalStack, Azurite, and pgvector containers instead of fakes -- `pytest.mark.e2e`, excluded
from the default suite. See `tests/ext/rag/test_pipeline_integration.py` (a full ingest -> validate
-> activate -> query run through real S3-compatible storage and real pgvector; a same-version
re-run proving avoided recomputation; and -- the literal headline crash/resume scenario -- a real
worker *process* hard-killed mid-run via `FailureInjector`, with a second, fresh worker process
resuming the same in-flight Dapr Workflow instance) and
`tests/ext/rag/test_sources_azure_blob_integration.py` (list/get/metadata against real Azurite)
for the exact `docker run` commands and `uv run pytest ... -m e2e` invocations -- each file's
module comment has both.

## Event-driven ingestion

Two triggering paths, one per provider (see `dapr/ext/rag/triggers.py` for the normalization
functions and `examples/rag/pubsub_trigger.py` / `pubsub_trigger_servicebus.py` for runnable Dapr
pub/sub subscribers):

- **S3**: Blob change -> SNS/SQS or EventBridge -> a Dapr pub/sub component -> `parse_s3_event_notifications`.
- **Azure**: Blob change -> Event Grid -> Azure Service Bus -> the Dapr Service Bus Topics pub/sub
  component -> `parse_azure_blob_event` (handles both Event Grid and CloudEvents schema).

Both paths normalize into the same `SourceChangeEvent`. Because delivery is at-least-once and can
arrive out of order, `EventDeduplicator` records each event's ID in Dapr state before acting on it,
and `reconciliation_workflow.ReconciliationTrigger` debounces a burst of events into a single,
prefix-level reconciliation run shortly after the burst goes quiet -- discovery against the real
source (not the event stream) remains the source of truth for what actually needs indexing. See
that module's docstring for the single-process limitation of its `threading.Timer`-based debounce
and the Dapr-Workflow-based alternative for a multi-replica subscriber deployment.

## Running the failure/recovery demo

See `examples/rag/README.md`'s "Failure and resume demo" section for the exact commands: set one
`RAG_DEMO_FAIL_*` environment variable, start the worker, start an ingestion run, watch the worker
hard-exit partway through, restart the *same* worker (with the demo variable unset), and watch
`python3 cli.py status` show the run complete without re-embedding the documents processed before
the crash.

## Azure-native flagship path

For the complete Azure Blob -> Azure OpenAI -> Azure AI Search -> hybrid retrieval -> Azure OpenAI
grounded answer path, see:

- [`examples/rag/README.md`](../../examples/rag/README.md) -- the runnable end-to-end sample and its 10 demonstrated steps.
- [`examples/rag/infra/`](../../examples/rag/infra) -- Bicep to provision the Azure resources (not validated against a real subscription -- see its README).
- [`docs/rag/azure-rbac.md`](azure-rbac.md) -- exact role assignments for the ingestion vs. query identities.
- [`docs/rag/observability.md`](observability.md) -- OpenTelemetry spans, correlation IDs, and Azure Monitor export.
- [`docs/rag/integrated-vectorization-alternative.md`](integrated-vectorization-alternative.md) -- why `DurableRAGPipeline` keeps ingestion in Dapr Workflow instead of an Azure AI Search indexer/skillset (a design note, not shipped code).
- [`docs/rag/foundry-iq.md`](foundry-iq.md) -- optional, feature-flagged Foundry IQ knowledge-source registration (`DurableRAGPipeline(foundry_iq_knowledge_source=...)`).

## Current MVP limitations

- **No local/offline emulator for Azure AI Search or (Azure) OpenAI.** Unlike S3/Blob, which have a
  real, opt-in `pytest.mark.e2e` integration profile against LocalStack/Azurite/pgvector (see
  "Local development with LocalStack and Azurite" above), these two adapters are verified only via
  dependency-injected fakes in the unit test suite, not against a real service -- see
  `examples/rag/README.md`'s "What this example does not automate" section for exactly what has
  and hasn't been run against real services.
- **Multi-tenancy fields are pass-through, not enforced.** `AzureAISearchVectorStore`'s schema
  includes `tenant_id`/`authorization_groups`, but the pipeline itself has no tenancy concept;
  populating them (e.g. via a custom parser/splitter tagging `Document.metadata`) and enforcing
  them at query time is left to the caller.
- **The event-driven reconciliation trigger is single-process.** See
  `reconciliation_workflow.py`'s docstring for the multi-replica alternative.
- **No automatic deletion of old index versions** (by design -- out of scope for this MVP; nothing
  stops you from deleting an old pgvector version's rows, a Pinecone namespace, or an old Azure AI
  Search index yourself once you're confident it's no longer needed).
- **No cross-vector-store migration, generic Dapr vector-store building block, or LLM-based
  reranking** -- all explicitly out of scope; see `dapr/ext/rag/AGENTS.md`.
- **OpenTelemetry instrumentation is a specification, not shipped code.** `docs/rag/observability.md`
  documents the span names/attributes an integrator should add; `dapr.ext.rag` does not create any
  of them itself today.
