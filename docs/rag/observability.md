# Observability

This document covers the OpenTelemetry spans `DurableRAGPipeline` and its query path should emit,
how to export them (plus logs/metrics) to Azure Monitor / Application Insights, and how to trace
one blob change through the entire pipeline using the resulting telemetry.

It assumes a Python process already instrumented with OpenTelemetry (Dapr's own gRPC/HTTP client
calls and the workflow runtime produce their own spans independently of this document) and
describes the *pipeline-specific* spans layered on top -- the ones that make it possible to answer
"what happened to this one document/chunk/query" rather than just "what did the SDK call."

**Status: specification, not shipped code.** `dapr.ext.rag` does not currently create any of the
spans below itself -- there is no `opentelemetry` import anywhere in the extension. Everything past
this point is a naming/attribute reference for an integrator to instrument their own worker/query
process against (e.g. by wrapping the `_activity_*` calls or the retrieval/generation calls with the
spans described here), not a description of built-in behavior. Treat the span names and attribute
keys as the recommended contract to converge on, not as something you will already see in a trace
if you export telemetry from an unmodified pipeline today.

## Span reference

| Span | Emitted by | When |
|---|---|---|
| `rag.discover_and_manifest` | Ingestion (orchestrator's first activity) | Once per workflow run: lists the source, builds and persists the manifest |
| `rag.process_document` | Ingestion (per-document activity) | Once per document, fanned out (bounded) per manifest page |
| `rag.embed_batch` | Ingestion (nested within `rag.process_document`) | Once per embedding-batch call to Azure OpenAI |
| `rag.vector_upsert` | Ingestion (nested within `rag.process_document`) | Once per upsert call to Azure AI Search |
| `rag.validate_version` | Ingestion (orchestrator activity) | Once per version, before activation |
| `rag.activate_version` | Ingestion (orchestrator activity) | Once per version, after validation passes |
| `rag.query.retrieve` | Query API | Once per query request: the Azure AI Search leg |
| `rag.query.generate_answer` | Query API | Once per query request: the chat-completion leg |

### Attributes

Shared attributes (used across several spans):

| Attribute | Meaning |
|---|---|
| `dapr.workflow.instance_id` | The Dapr Workflow orchestration instance ID -- the durable correlation key for one ingestion run (see the correlation narrative below) |
| `rag.pipeline_id` | Pipeline identity (defaults to the vector store's index base name) |
| `rag.version` | The version string being ingested, validated, activated, or queried |
| `rag.document.id` | Source document identity (source-specific: blob name or S3 key) |
| `rag.batch.id` | Pipeline-generated logical identifier for one embedding/upsert batch |
| `azure.openai.deployment` | Azure OpenAI deployment name called |
| `azure.openai.request_id` | Request ID from the Azure OpenAI response. Azure OpenAI commonly surfaces both `x-request-id` and (when fronted by API Management) `apim-request-id`; capture whichever your HTTP client exposes -- for the official SDK's non-streaming responses this is available as a property on the top-level response object, otherwise attach an HTTP client hook to read response headers directly |
| `azure.search.index_name` | Physical index name (`{index_base_name}-{version}`) being written to or read from |
| `azure.search.alias_name` | The stable alias (`{index_base_name}-active` by default) |
| `azure.search.request_id` | The `x-ms-request-id` Azure AI Search returns for the specific HTTP call |

Per-span attributes:

- **`rag.discover_and_manifest`**: `rag.eventgrid.event_id`, `messaging.message.id` (both absent for
  a manually-started run -- see the correlation narrative), `rag.source.type` (`s3` | `azure_blob`),
  `rag.manifest.document_count`, `rag.manifest.page_count`.
- **`rag.process_document`**: `rag.document.content_hash` (the hash used for the idempotency check
  -- never the content itself), `rag.attempt`, `rag.document.chunk_count`, `rag.document.outcome`
  (`completed` | `failed` | `skipped_already_complete`).
- **`rag.embed_batch`**: `rag.batch.chunk_count`.
- **`rag.vector_upsert`**: `rag.batch.chunk_count`, and the batch's first/last `rag.chunk.id` rather
  than the full list (see the cardinality note below).
- **`rag.validate_version`**: `rag.validation.document_count`, `rag.validation.passed` (bool),
  `rag.validation.failure_reason` (a short code such as `"empty_manifest"`, never a message that
  embeds document content).
- **`rag.activate_version`**: `rag.activation.was_noop` (bool -- true when this `(version,
  manifest_hash)` was already active, i.e. the activity's no-op path).
- **`rag.query.retrieve`**: `rag.query.request_id` (an app-generated correlation ID for one query
  request, independent of any ingestion run's workflow instance ID), `rag.query.top_k`,
  `rag.retrieval.mode` (`hybrid` | `vector` | `keyword`), `rag.retrieval.result_count`.
- **`rag.query.generate_answer`**: `rag.query.request_id`, `rag.answer.citation_count`.

**Cardinality note.** A `rag.vector_upsert` span can cover many chunks in one batch. Attach a
count and the first/last chunk ID rather than the full ID list as a single attribute -- if you need
true per-chunk granularity, add a [span event](https://opentelemetry.io/docs/concepts/signals/traces/#span-events)
per chunk ID instead of growing one attribute unboundedly.

### What must never be a span attribute

**Never attach document content, chunk text, prompts, or generated answers to a span**, as an
attribute, an event, or a span name. This includes: the text passed to the embeddings API, the
chat prompt (including any retrieved-context stanza built for it), the generated answer, and raw
document bytes/text at any pipeline stage. Reasons this is a hard rule, not a style preference:

- Traces are typically retained, indexed, and access-controlled far more loosely than the
  documents the pipeline ingests -- attaching content to a span silently widens that content's
  blast radius to everyone with trace-read access (which, in Application Insights, is often a
  broader group than everyone with source-data access).
- Span attribute values have practical size limits and are billed as ingested telemetry volume in
  Azure Monitor; document/chunk text can be arbitrarily large.
- IDs and hashes (`rag.document.id`, `rag.document.content_hash`, `rag.chunk.id`) already give you
  everything you need to correlate a trace with the actual content in its source system of record
  (the blob, the search index) without duplicating that content into telemetry.

If you need content-level debugging, use a separate, explicitly opt-in, access-controlled debug
log sink (and make sure whoever operates it understands it now holds a copy of potentially
sensitive document content) -- never the tracing pipeline.

## Correlation-ID propagation: tracing one blob through the whole pipeline

One blob change accumulates several different identifiers on its way through the system. They are
**not the same value** at each hop, and treating them as interchangeable is the most common way to
lose the thread when debugging in Application Insights. In order:

1. **Event Grid event ID.** When a blob is created/updated, Event Grid emits an event with its own
   `id` field (`rag.eventgrid.event_id`). This ID is scoped to Event Grid -- it shows up in Event
   Grid's own delivery diagnostics.
2. **Service Bus message ID.** Event Grid delivers that event as the *body* of a message it
   publishes to the Service Bus topic. That message gets its own transport-level `MessageId`
   (`messaging.message.id`, using the OpenTelemetry messaging semantic convention name) --
   independent of the Event Grid event ID, and the one visible in Service Bus's own diagnostic
   logs and metrics.
3. **Dapr's pub/sub envelope ID.** Dapr's Service Bus pub/sub component delivers the message to
   the app wrapped in a CloudEvents envelope. Dapr's envelope carries its own `id`, which can differ
   from both of the above (Dapr assigns a fresh one unless the inbound message already parses as a
   valid CloudEvent). Capture all three IDs -- Event Grid event ID, Service Bus message ID, and
   Dapr envelope ID -- at the trigger boundary rather than assuming any two of them match.
4. **Dapr Workflow instance ID.** The trigger handler starts (or signals) a workflow instance.
   From here on, `dapr.workflow.instance_id` is the **durable** correlation key for the rest of the
   run: it survives worker crashes and pod restarts (durabletask's own recovery reconnects to the
   same instance ID on restart), unlike the three upstream message IDs, which only matter for the
   initial hop. `rag.discover_and_manifest`'s span should record all four IDs from steps 1-4
   together, once, so later spans only need to carry the workflow instance ID.
5. **Per-document and per-chunk IDs.** `rag.process_document` carries `rag.document.id`;
   `rag.embed_batch` and `rag.vector_upsert` carry `rag.batch.id` and chunk IDs, all nested under
   the same `dapr.workflow.instance_id` trace.
6. **Azure OpenAI and Azure AI Search request IDs.** `rag.embed_batch` carries the
   `azure.openai.request_id` for that embedding call; `rag.vector_upsert` carries the
   `azure.search.request_id` for that upsert call. These are what you hand to Azure support (or use
   in the respective service's own diagnostic logs) if you suspect a service-side issue rather than
   a pipeline bug.
7. **Activation.** `rag.activate_version` ties the whole run to the alias switch, recording which
   physical index (`azure.search.index_name`) the alias (`azure.search.alias_name`) now points to.

**Query-time traces are independent.** A query request starts a *new* trace
(`rag.query.request_id`) with no causal link back to any specific ingestion run -- it queries
whatever the alias currently points to, and the documents a single query touches may have been
written by several different ingestion runs over time. To find out which ingestion run produced a
document a query retrieved, join on that document's own provenance metadata (the
`ProvenanceRecord` fields -- pipeline ID, workflow instance ID, source content hash -- stored
alongside every vector; see `dapr/ext/rag/AGENTS.md`'s provenance note) returned with the search
result, not on trace context.

## Exporting to Azure Monitor / Application Insights

Use the [`azure-monitor-opentelemetry`](https://pypi.org/project/azure-monitor-opentelemetry/)
distro package, which wires up the OpenTelemetry SDK's trace/log/metric exporters for Application
Insights in one call. The connection string is the Bicep output
`appInsightsConnectionString` from [`examples/rag/infra`](../../examples/rag/infra).

```sh
pip install azure-monitor-opentelemetry
```

```python
# Illustrative minimal setup -- call this once, at process startup, before
# creating any tracer or starting the Dapr Workflow runtime/query API.
import os

from azure.monitor.opentelemetry import configure_azure_monitor

configure_azure_monitor(
    # Falls back to the APPLICATIONINSIGHTS_CONNECTION_STRING environment
    # variable automatically if this kwarg is omitted.
    connection_string=os.environ["APPLICATIONINSIGHTS_CONNECTION_STRING"],
)
```

`configure_azure_monitor()` also auto-instruments common libraries (`requests`, `httpx`, etc.), so
the underlying HTTP calls Dapr's client SDK, `azure-search-documents`, and the Azure OpenAI SDK
make are exported alongside the pipeline's own spans without additional setup. From there, create
this pipeline's own spans with the standard OpenTelemetry API and set the attributes from the
reference above:

```python
from opentelemetry import trace

tracer = trace.get_tracer("dapr.ext.rag")

with tracer.start_as_current_span("rag.process_document") as span:
    span.set_attribute("dapr.workflow.instance_id", instance_id)
    span.set_attribute("rag.pipeline_id", pipeline_id)
    span.set_attribute("rag.version", version)
    span.set_attribute("rag.document.id", document_id)
    ...
```

For production traffic volumes, pair this with a
[sampler](https://opentelemetry.io/docs/languages/python/sdk/#sampling) appropriate to your ingest
budget -- Application Insights bills on ingested telemetry volume, and a busy ingestion run can
generate a `rag.embed_batch`/`rag.vector_upsert` span per batch across a large corpus.

## Finding one blob's trace in Application Insights

With the above in place, a typical investigation ("what happened to `policies/handbook.pdf`?")
looks like:

1. **Transaction search** for the known `rag.document.id` (or the Event Grid event ID, if that is
   all you have) as a custom-dimension filter -- this surfaces the specific `rag.process_document`
   span (and, through trace context, its parent `dapr.workflow.instance_id`).
2. **Application Map / end-to-end transaction view** on that trace to see every nested
   `rag.embed_batch` and `rag.vector_upsert` span, each with its own
   `azure.openai.request_id`/`azure.search.request_id` for cross-referencing with the respective
   service's own diagnostic logs if needed.
3. A **Log Analytics (KQL) query** joining on `dapr.workflow.instance_id` across
   `customEvents`/`dependencies`/`traces` tables gives the full run, including
   `rag.validate_version` and `rag.activate_version`, to confirm whether (and when) this document's
   version actually went live behind the alias.
