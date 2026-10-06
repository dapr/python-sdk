# Foundry IQ integration

`dapr.ext.rag` can register a validated Azure AI Search index produced by `DurableRAGPipeline`
as a Foundry IQ knowledge source. This is **opt-in and off by default**, and it does not
duplicate Foundry IQ's own retrieval engine -- see "What this integration does and does not do"
below before enabling it.

**Preview-dependent, verify before relying on this.** Foundry IQ and Azure AI Search's agentic
retrieval feature are moving quickly. The terminology, API surface, and GA/preview split below
were checked against Microsoft Learn on **2026-09-10** (cited inline); by the time you read this,
names, capabilities, or availability may have changed. Re-verify against current docs before
depending on this in production.

## What Foundry IQ and knowledge sources are

[Foundry IQ](https://learn.microsoft.com/azure/foundry/agents/concepts/what-is-foundry-iq) is
Microsoft's managed knowledge layer for AI agents, built on Azure AI Search. A **knowledge base**
is the top-level resource an agent queries; it references one or more **knowledge sources**
(connections to indexed or remote content -- Blob Storage, SharePoint, OneLake, an existing Azure
AI Search index, the web, or MCP in private preview) and holds retrieval parameters. At query
time, **agentic retrieval** decomposes a question into subqueries, runs them in parallel,
semantically reranks the results, and returns a grounded, cited answer -- optionally using an LLM
for the query-planning step.

Microsoft Learn's own note as of this writing: "Some Foundry IQ features are now generally
available, while others remain in preview. Availability depends on the Search Service REST API
version you use." Concretely: creating a **search index knowledge source** (the kind this
integration uses -- see below) is GA as of the `2026-04-01` REST API; `semanticConfigurationName`
is required on that API version and optional starting with `2026-05-01-preview`; and the portal
experience for all of this remains preview regardless of REST API version. Source:
[Create a Search Index Knowledge Source](https://learn.microsoft.com/azure/search/agentic-knowledge-source-how-to-search-index).

## How to use it

```python
from dapr.ext.rag import DurableRAGPipeline, FoundryIQKnowledgeSourceConfig

pipeline = DurableRAGPipeline(
    source=..., parser=..., splitter=..., embedder=...,
    vector_store=...,  # must be AzureAISearchVectorStore
    state_store_name="rag-pipeline-state",
    foundry_iq_knowledge_source=FoundryIQKnowledgeSourceConfig(
        name="company-knowledge-ks",
        source_data_fields=("title", "source_uri"),
        search_fields=("content",),
    ),
)
```

With this set, every successful activation -- from `pipeline.start(activate_when_complete=True)`
or `pipeline.activate_version(...)` -- runs one additional, durable workflow activity right after
`activate_version` succeeds: `AzureAISearchVectorStore.register_foundry_iq_knowledge_source`
creates or updates the named knowledge source to point at that version's concrete physical index.
Like `pubsub_name`'s activation-event publish, registration is **best-effort**: a failure is
logged, never raised, so it never fails an otherwise-successful activation (Foundry IQ
registration is a convenience on top of a validated, active index, not a precondition for one).

`AzureAISearchVectorStore.register_foundry_iq_knowledge_source` requires
`semantic_configuration_name` to be set on that store (the `2026-04-01` REST API this method
targets requires it on every search index knowledge source), and is itself idempotent -- calling
it again with the same version is a no-op, matching `activate_version`'s own idempotency.

## Why this talks to a REST endpoint, not the SDK

Microsoft's own docs illustrate knowledge-source creation as an `azure-search-documents` SDK
call (`SearchIndexClient.create_or_update_knowledge_source(...)`). As of `azure-search-documents`
11.6.0 (confirmed by introspecting the installed package on 2026-09-10), neither
`SearchIndexKnowledgeSource`/`SearchIndexKnowledgeSourceParameters` nor that client method exist
-- the feature is GA at the REST layer but not yet wrapped by this SDK version. This is the same
situation as index aliases (see `dapr/ext/rag/AGENTS.md`'s "Azure AI Search: index aliases are
REST-only, not SDK-only"), and the fix is the same: `register_foundry_iq_knowledge_source` talks
to the Search REST API directly (`PUT {endpoint}/knowledgesources('{name}')?api-version=2026-04-01`),
reusing the exact same `httpx` transport, credential, and headers the alias calls already use.
Verified against Microsoft's REST API reference
([Knowledge Sources - Create or Update](https://learn.microsoft.com/rest/api/searchservice/knowledge-sources/create-or-update))
on 2026-09-10. If a future `azure-search-documents` release adds real SDK support, only this one
method's implementation needs to change -- its signature and behavior would not.

## Why this targets the concrete physical index, not the alias

**This is a real operational hazard, not just a naming detail.** A search index knowledge
source's `searchIndexParameters.searchIndexName` takes a specific index name; every example in
Microsoft's own docs uses a concrete name like `"my-search-index"`, never an alias. Whether the
underlying knowledge-source resource *resolves* an alias dynamically (re-checking on every
retrieval) or *binds* to whatever physical index the alias pointed to at creation time is not
documented anywhere this note's research could confirm -- `register_foundry_iq_knowledge_source`
therefore assumes the more dangerous case (that it binds once) and always re-points the knowledge
source explicitly to `{index_base_name}-{version}` on every activation, the same way
`activate_version` re-points the alias itself. Registering a knowledge source against the alias
name instead would risk leaving it silently pointing at a stale, superseded index after this
pipeline's next version activation flips the alias -- the exact class of staleness bug this
pipeline's whole alias-based design exists to prevent for direct queries.

## What this integration does and does not do

- It **does** durably coordinate creating/updating the knowledge source as a workflow activity,
  chained strictly after `activate_version` succeeds -- never for a version that has not passed
  this pipeline's own validation gate.
- It does **not** duplicate Foundry IQ's own query-planning or retrieval engine. This pipeline's
  `ActiveVersionResolver`/`AzureAISearchVectorStore.query()` (hybrid Azure AI Search retrieval)
  and `AzureOpenAIChatClient` (direct Azure OpenAI chat completion) are one query path; Foundry
  IQ's agentic retrieval against the registered knowledge source is a separate, alternative one
  against the same underlying index. A deployment picks one per use case; this integration's job
  stops at handing over a validated index and keeping a knowledge source pointed at the current
  one -- never at re-implementing multi-query planning or reranking Foundry IQ already provides.
- It does **not** create a knowledge source of any kind other than `searchIndex` (wrapping an
  already-built index). A knowledge source that owns its own indexer/skillset against a raw
  source is a *different*, uncoordinated ingestion path into the same search service -- exactly
  what this pipeline's durable-workflow design is meant to be the single source of truth against
  for its own indexes. (Compare `docs/rag/integrated-vectorization-alternative.md`, which
  discusses Azure AI Search's indexer/skillset-based ingestion as a deliberate, wholesale
  *alternative* to `DurableRAGPipeline` -- not something this package ships or composes with it.)

## Sources

- [What is Foundry IQ?](https://learn.microsoft.com/azure/foundry/agents/concepts/what-is-foundry-iq)
- [Create a Search Index Knowledge Source](https://learn.microsoft.com/azure/search/agentic-knowledge-source-how-to-search-index)
- [Knowledge Sources - Create or Update (REST)](https://learn.microsoft.com/rest/api/searchservice/knowledge-sources/create-or-update)
- [Connect an Azure AI Search index to Foundry agents](https://learn.microsoft.com/azure/foundry/agents/how-to/tools/ai-search)
