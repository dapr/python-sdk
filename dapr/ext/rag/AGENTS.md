# AGENTS.md — dapr.ext.rag

The RAG extension provides `DurableRAGPipeline`: a Dapr Workflow orchestration that discovers
documents from a cloud object store, parses and chunks them, generates embeddings, and writes
them into a versioned vector index -- surviving throttling, process crashes, and pod restarts by
resuming from completed work rather than reprocessing everything, and never exposing a
partially-built index to queries.

## Source layout

```
dapr/ext/rag/
├── __init__.py              # Public API exports (see below)
├── py.typed
├── models.py                 # Every typed dataclass shared across this extension
├── errors.py                  # RagError hierarchy; RetryableError vs NonRetryableError
├── fingerprints.py             # Deterministic SHA-256 hashing (content, config, chunk IDs)
├── _wire.py                     # dataclass <-> dict conversion at the activity boundary
├── splitting.py                  # DocumentSplitter ABC + TextSplitter
├── state.py                       # PipelineStateStore: all Dapr state access, incl. the
│                                    ETag-guarded ActivationRecord CAS (see "Version activation")
├── retrieval.py                    # ActiveVersionResolver: resolve + query, for reader processes
├── generation.py                    # AzureOpenAIChatClient: query-time cited-answer generation
├── pipeline.py                      # DurableRAGPipeline: orchestrator, activities, public API
├── triggers.py                       # S3/Azure event-notification parsing + SourceChangeEvent
│                                       normalization + EventDeduplicator (for pub/sub triggers)
├── testing.py                         # FailureInjector (demo/test-only crash simulation)
├── sources/
│   ├── base.py                         # DocumentSource ABC
│   ├── s3.py                           # S3Source (boto3, optional)
│   └── azure_blob.py                    # AzureBlobSource (azure-storage-blob/-identity, optional)
├── parsing/
│   ├── base.py                          # DocumentParser ABC
│   ├── unstructured.py                   # UnstructuredParser (unstructured, optional)
│   └── langchain.py                       # to/from_langchain_documents (langchain-core, optional)
├── embedding/
│   ├── base.py                           # Embedder ABC
│   ├── _openai_common.py                  # Shared OpenAI/Azure OpenAI response parsing + error
│   │                                        classification + Azure client construction
│   ├── openai.py                          # OpenAIEmbedder (openai, optional)
│   └── azure_openai.py                    # AzureOpenAIEmbedder (openai + azure-identity, optional)
└── vector_stores/
    ├── base.py                            # VectorIndex ABC (+ activate_version, see below)
    ├── pgvector.py                        # PgVectorStore (psycopg, optional)
    ├── pinecone.py                        # PineconeVectorStore (pinecone, optional)
    └── azure_ai_search.py                 # AzureAISearchVectorStore (azure-search-documents +
                                             # httpx, optional), incl. register_foundry_iq_
                                             # knowledge_source -- see "Azure AI Search: index
                                             # aliases are REST-only" and "Foundry IQ" below
                                             # before touching this file

tests/ext/rag/               # Unit tests, one file per module above (unittest.TestCase, mocked I/O),
                              # plus a real, opt-in `pytest.mark.e2e` profile -- see "Testing" below
examples/rag/                # Runnable worker + CLI + failure demo + pub/sub trigger example
```

Installed via the `rag` extra plus whichever adapters you need, e.g.
`pip install "dapr[rag,rag-s3,rag-pgvector]"` or `pip install "dapr[rag,rag-azure,rag-pinecone]"`.

## Architecture

```
┌────────────────────────────────────────────────────────────────────┐
│ DurableRAGPipeline (pipeline.py)                                    │
│  .start()/.activate_version()  →  DaprWorkflowClient.schedule_*      │
│  .get_status()/.resolve_active_version()  →  PipelineStateStore reads│
└───────────────────────────────┬──────────────────────────────────────┘
                                │ schedules
┌───────────────────────────────▼──────────────────────────────────────┐
│ rag_ingest orchestrator (deterministic generator; _orchestrate_ingestion)
│  1. discover_and_manifest (once)      5. validate_version              │
│  2. get_manifest_batch (per page)     6. activate_version                │
│  3. process_document x N (bounded)    7. publish_activation_event         │
│  4. update_status                     8. continue_as_new per batch          │
└───────────────────────────────┬──────────────────────────────────────┘
                                │ call_activity (all I/O lives here)
        ┌───────────────────────┼────────────────────────┬─────────────────┐
        ▼                       ▼                        ▼                 ▼
  DocumentSource          DocumentParser +          Embedder           VectorIndex
  (S3 / Azure Blob)       DocumentSplitter          (OpenAI)      (pgvector / Pinecone)
        │                                                                   │
        └──────────────────────────► PipelineStateStore (state.py) ◄────────┘
                     manifest pages, completion records, embed progress,
                     pipeline status, ETag-guarded activation pointer
```

Every arrow crossing into an adapter or `PipelineStateStore` happens **inside a workflow
activity** (`pipeline.py`'s `_activity_*` methods) -- never in the orchestrator generator, which
must stay deterministic (see `dapr/ext/workflow/AGENTS.md`'s determinism rules). The orchestrator
never reads `datetime.now()` (it uses `ctx.current_utc_datetime`), never calls an adapter
directly, and never reads or writes Dapr state directly.

## Why these adapter interfaces, and why `query()` was added

`sources/base.py`, `parsing/base.py`, `vector_stores/base.py` follow the shapes sketched in this
extension's design brief (`list_documents`/`get_document`/`get_metadata`,
`parse(content, ...)`, `upsert`/`delete_document`/`validate_version`), adapted in two ways:

- `DocumentParser.parse` takes the richer `SourceDocument` rather than just `SourceMetadata`,
  since a parser needs the document's *name* (for extension-based format detection), which lives
  on `SourceDocument`, not `SourceMetadata`.
- `VectorIndex` gained a `query()` method beyond the brief's write-only sketch: retrieval (the
  sample CLI's `query` command, and `retrieval.ActiveVersionResolver`) needs *some* similarity
  search, and adding it to the ABC is what keeps that search provider-agnostic rather than
  branching on `pgvector` vs. `pinecone` in a reader.
- `VectorIndex` also gained `activate_version(version, *, previous_version)`, a no-op by default.
  For pgvector/Pinecone, the Dapr-state `ActivationRecord` alone *is* activation (see "Version
  activation" below). `AzureAISearchVectorStore` overrides it because, there, a version is a whole
  separate physical index rather than a column/namespace -- see "Azure AI Search: index aliases are
  REST-only, not SDK-only" below for what that override actually does and why it exists at all.

No `dapr.ext.rag` component existed before this extension, and there is no separate
"Dapr Agents" package in this repository to reuse from -- these ABCs, `OpenAIEmbedder`, etc. were
written fresh, following this repo's conventions (dataclasses, `logging.getLogger(__name__)`,
per-adapter optional-import guards).

## Public API

```python
from dapr.ext.rag import (
    DurableRAGPipeline, PipelineConfig,
    S3Source, AzureBlobSource,
    UnstructuredParser, TextSplitter, OpenAIEmbedder,
    PgVectorStore, PineconeVectorStore,
    ActiveVersionResolver,
)

pipeline = DurableRAGPipeline(
    source=S3Source(bucket='company-docs', prefix='policies/'),
    parser=UnstructuredParser(),
    splitter=TextSplitter(chunk_size=1000, chunk_overlap=150),
    embedder=OpenAIEmbedder(model='text-embedding-3-small'),
    vector_store=PgVectorStore(connection_string='...', collection='company-knowledge'),
    state_store_name='rag-pipeline-state',
)
pipeline.run_worker()  # in the worker process; a client-only process skips this
instance_id = pipeline.start(version='2026-09', activate_when_complete=True)
status = pipeline.get_status('2026-09')
active = pipeline.resolve_active_version()
```

See `examples/rag/README.md` for the full worker/CLI/failure-demo walkthrough and
`docs/rag/README.md` for architecture, configuration, and operational documentation.

## Optional-dependency guard pattern (deliberately *not* the langgraph/strands pattern)

`dapr.ext.langgraph`/`dapr.ext.strands` each wrap exactly one third-party SDK, so they guard the
import once, in `__init__.py` (try/except around the whole implementation import, re-raising with
an install hint if the *specific* missing module matches). `dapr.ext.rag` bundles **several
independent** optional adapters (boto3, azure-storage-blob/-identity, openai, psycopg, pinecone,
unstructured, langchain-core) -- guarding only in `__init__.py` would mean the first missing
package breaks `import dapr.ext.rag` entirely, even for a user who only needs pgvector.

So each adapter module guards its own import instead, e.g. `sources/s3.py`:
```python
try:
    import boto3
except ImportError:
    boto3 = None
```
and raises `OptionalDependencyError` lazily, from the class's `__init__`, only when neither the
package nor an injected `client=`/`connection_factory=` is available. `dapr/ext/rag/__init__.py`
therefore imports every adapter module unconditionally, and always succeeds regardless of which
optional packages are installed.

## Idempotency and recovery (the core value proposition)

State store key schema (see `state.py` for the exact key builders):

| Key pattern | Contents |
|---|---|
| `rag:manifest:{pipeline_id}:{version}:meta` | `ManifestSummary` + page/document counts |
| `rag:manifest:{pipeline_id}:{version}:page:{n}` | One page of `DocumentWorkItem` (also the fan-out batch source) |
| `rag:completion:{pipeline_id}:{version}:{document_id}` | `CompletionRecord` -- the idempotency check |
| `rag:embed-progress:{pipeline_id}:{version}:{document_id}` | `EmbedProgressRecord` -- which embedding batches are durably upserted |
| `rag:attempts:{pipeline_id}:{version}:{document_id}` | Attempt counter, for the retry-count metric |
| `rag:status:{pipeline_id}:{version}` | `PipelineStatus` -- what `get_status()` reads |
| `rag:activation:{pipeline_id}` | `ActivationRecord`, ETag-guarded |

Recovery relies on two independent mechanisms:

1. **durabletask's own crash recovery.** Orchestration state lives in the Dapr-managed backend,
   not the worker process. If the worker process crashes mid-run, restarting it (same instance ID)
   reconnects and durabletask redelivers any work item that didn't record a result -- no
   application code needed. This is what `examples/rag/failure_demo.py` demonstrates: kill the
   worker, restart it, watch the same instance resume.
2. **Per-document idempotency in Dapr state**, for the case durabletask's own recovery doesn't
   cover: a brand-new workflow instance re-processing the same `version` (e.g. after a prior
   instance reached a terminal FAILED/TERMINATED state). `process_document` checks
   `CompletionRecord` (keyed by `source_content_hash` + `pipeline_fingerprint`) before doing any
   real work, and checks `EmbedProgressRecord` per embedding batch before re-embedding. A
   completion record is written **only after** its vectors are durably upserted -- see
   `pipeline.py::_process_one_document`'s comment on write ordering -- so "crashed after embedding,
   before recording completion" always re-embeds at most one in-flight batch, never silently loses
   or duplicates a whole document's work. Vector upserts are idempotent through the deterministic
   chunk IDs computed by `fingerprints.compute_chunk_id`.

**Retryable vs. non-retryable classification is hand-rolled, deliberately.** `dapr.ext.workflow`'s
public `RetryPolicy` has no supported way to mark an exception type non-retryable (the vendored
durabletask engine has one, `NonRetryableError`/`non_retryable_error_types`, but it isn't
re-exported and importing `_durabletask` from outside the extension is unsupported -- see
`dapr/ext/workflow/AGENTS.md`). So `errors.py` defines its own `RetryableError`/`NonRetryableError`
split, and `pipeline.py::_activity_process_document` catches accordingly: a `RetryableError`
re-raises (engaging the activity's `RetryPolicy`); a `NonRetryableError` is caught and turned into
a `DocumentOutcome(status='failed', retryable=False)` so the activity returns normally instead of
burning retry budget on a failure retrying can't fix.

**Bounded fan-out without `when_all`.** The orchestrator schedules an entire manifest page's
worth of `process_document` calls up front (the fan-out, bounded to `max_concurrent_documents`),
then `yield`s each task *individually* in a loop rather than via `wf.when_all(...)`. This is
deliberate: `process_document` never raises for an *expected* failure (see above), so a raised
exception at that point only ever means retries were exhausted or something truly unexpected
happened -- and because every task was already scheduled together, every other document in the
batch has already run to completion (including recording its own state) by the time we get there.
Catching per-task lets `fail_fast=False` (the default) collect that batch's results and move on
without one document's failure discarding its siblings' outcomes.

**History size**: after each batch, the orchestrator calls `ctx.continue_as_new(...)` with a small,
flat cursor state (`_IngestionState`) rather than accumulating the manifest or every batch's
results in workflow history -- the same pattern `examples/workflow/monitor.py` uses for an eternal
polling workflow. History size per generation stays bounded regardless of total corpus size.

**Dataclasses, not pydantic, across the activity boundary.** `dapr.ext.workflow`'s automatic
input/output coercion (`_model_protocol.py`) only recognizes pydantic-v2-shaped classes
(`model_dump`/`model_validate`). This extension uses plain `@dataclass` types throughout, matching
the rest of the SDK, so `_wire.py`'s `to_wire`/`from_wire` do that conversion explicitly at each
`call_activity`/`continue_as_new` boundary. Every dataclass that crosses that boundary must stay
*flat* (JSON-primitive fields only) -- see `_wire.py`'s module comment for why a nested dataclass
field wouldn't survive the round trip.

## Version activation

`ActivationRecord` (in `models.py`) is a single JSON value at `rag:activation:{pipeline_id}`,
updated via a plain ETag-conditional `save_state` (not a multi-key transaction) -- deliberately,
so activation only requires the widely-supported per-key ETag/concurrency state-store capability,
not the less commonly supported multi-key transaction one. A conflicting concurrent write raises
Dapr's `ABORTED` status, which `state.py::write_activation` turns into `ActivationConflictError`
(a `RetryableError` -- re-running the activity re-reads the current ETag, so the workflow's own
`RetryPolicy` resolves the race without a bespoke inner loop). Repeated activation of the same
`(version, manifest_hash)` is a no-op (`_activity_activate_version` checks before writing).
`retrieval.ActiveVersionResolver` is the read-side counterpart: it reads the pointer with
`consistency: strong` and queries only the resolved version, so a reader never sees a
partially-built one.

## Azure AI Search: index aliases are REST-only, not SDK-only

`AzureAISearchVectorStore.activate_version` needs to atomically repoint an alias
(`{index_base_name}-active`) from one physical index to another -- but `azure-search-documents`'
`SearchIndexClient` has **no alias method at all**, in any installed or currently-released version.

This was not a deliberate design choice; it was discovered mid-implementation. Index aliases were
briefly in the SDK as a beta feature (`11.4.0b1`) but were removed before the stable `11.4.0`
release and have not been restored in any version since, up to and including `12.1.0b2` (verified
against the SDK's own `CHANGELOG.md` on 2026-09-10). The symptom, if you hit this again after an
SDK upgrade: importing `SearchAlias` from `azure.search.documents.indexes.models` raises
`ImportError` -- and because that import used to sit inside the same guarded `try/except ImportError`
block as every other schema/client class this module needs, *that one missing name silently made
the entire block fall back to its `except` branch*, setting `SimpleField` and friends to `None` even
though `azure-search-documents` genuinely was installed. That, in turn, made every
`AzureAISearchVectorStore` test using the real SDK skip via `_HAS_REAL_SDK`, for a reason that had
nothing to do with what those tests actually exercise. If a "why is everything skipping" mystery
like that shows up again, check for exactly this pattern before assuming the package isn't
installed: `python -c "import azure.search.documents.indexes.models"` and read `ImportError.name`
to find which single missing name is poisoning the whole block, rather than trusting the `except`
branch's own claim about why it was taken.

The fix: `activate_version`, `_alias_indexes`, and `_put_alias` talk to the Search REST API's
`/aliases('{name}')` operations directly via an injectable `httpx`-compatible transport
(`alias_transport=`), instead of going through `SearchIndexClient` at all -- verified against
Microsoft's REST API reference for `searchservice.aliases.createorupdate` on 2026-09-10.
Everything else this class does (index CRUD, document upsert/query) still goes through the real
SDK, since that surface *is* fully supported -- only alias management is REST-only. Auth for the
REST calls reuses whatever credential the constructor already resolved (`api-key` header for an
`AzureKeyCredential`, a bearer token via `credential.get_token(...)` otherwise), so callers never
configure Search auth twice. This is also why `endpoint` became a required constructor parameter
even when `index_client`/`search_client_factory` are fully injected: the alias REST calls need it
regardless of whether the SDK client was constructed at all.

Since there's no local Azure AI Search emulator, `AzureAISearchVectorStoreActivateVersionTest`
exercises this purely against `_FakeAliasTransport` (a `dict`-backed stand-in for the REST
endpoint) in `tests/ext/rag/test_vector_stores_azure_ai_search.py` -- it needs no real SDK and is
not `_HAS_REAL_SDK`-gated, unlike the schema-creation and query tests in the same file.

## Foundry IQ

`register_foundry_iq_knowledge_source` (a method on `AzureAISearchVectorStore`, wired into
`DurableRAGPipeline` as an opt-in constructor param, `foundry_iq_knowledge_source=`) --
`docs/rag/foundry-iq.md`. A workflow activity (`_activity_register_foundry_iq_knowledge_source`)
chained strictly after `activate_version` succeeds, in both `_orchestrate_ingestion` and
`_orchestrate_activation`. Best-effort like `_activity_publish_activation_event` -- a failure is
logged, never raised. `DurableRAGPipeline.__init__` rejects `foundry_iq_knowledge_source=` at
construction time (a `ValueError`, not a later activity failure) when `vector_store` doesn't
have this method, via `hasattr` -- checked once at startup rather than the activity discovering
it at run time. Like the alias calls in the section above, this talks to the Search REST API
directly (reusing the exact same `httpx` transport/credential/headers): Microsoft's own docs
illustrate knowledge-source creation as an `azure-search-documents` SDK call, but
`SearchIndexKnowledgeSource`/`SearchIndexKnowledgeSourceParameters` do not exist in
`azure-search-documents` 11.6.0 (confirmed by introspecting the installed package on
2026-09-10) -- the same SDK-lags-the-REST-API situation as aliases, discovered while
implementing this method.

**No `AzureSearchIntegratedVectorizationPipeline`.** Azure AI Search's own "integrated
vectorization" (indexers + skillsets that chunk/embed as part of indexing) was briefly
implemented as a class here and deliberately removed: it has no Dapr Workflow, Dapr client, or
Dapr sidecar involvement whatsoever (it is plain `azure-search-documents` SDK orchestration), and
shipping it as part of this Dapr extension misrepresented it as inheriting `DurableRAGPipeline`'s
durability guarantees, which it does not and cannot -- an indexer run's own internal
retry/recovery behavior is opaque to the caller, nothing like the per-document/per-batch
`CompletionRecord`/`EmbedProgressRecord` tracking below. `docs/rag/integrated-vectorization
-alternative.md` still documents it as a legitimate alternative *architecture* for teams who
decide they don't want Dapr Workflow's guarantees at all -- but as a design note to build from
scratch outside this package if you want it, not as shipped code here.

## Testing

```bash
uv run python -m unittest discover -v ./tests/ext/rag
```

Every adapter accepts an injectable client/connection (`client=`, `connection_factory=`,
`partition_fn=`, `index_client=`/`search_client_factory=`/`alias_transport=`) specifically so tests
exercise the real adapter logic against a mock/fake without needing live network access to the
corresponding third-party service -- mirroring `tests/ext/strands/test_session_manager.py`'s
`@mock.patch(...DaprClient)` pattern, applied per adapter instead of per extension. Every optional
package (`boto3`, `azure-*`, `openai`, `psycopg`, `pinecone`, `unstructured`, `langchain_core`) is
installed in the `dev` dependency group (via the `rag`/`rag-*` extras folded into `dapr[all]`), so
the full test run does exercise each adapter's real SDK types/classes -- what none of it does is
real network I/O: `S3Source` uses `botocore.stub.Stubber` against real `boto3` calls, and everything
else drives injected fakes end to end (see `_FakeAliasTransport` in
`test_vector_stores_azure_ai_search.py` for the least trivial example). A machine without any of
these packages installed still passes the full suite too -- each adapter's `OptionalDependencyError`
path is tested by patching its guarded import to `None`, not by uninstalling anything.

**`unstructured` is the one exception, and only on Windows**: `all` (`pyproject.toml`) excludes
`rag-unstructured` there via `sys_platform != 'win32'`. `unstructured` pulls in `python-magic`,
which needs a real libmagic to sniff file types -- Windows has none, and `python-magic`'s own
compat shim (`magic/compat.py`) crashes the whole interpreter with a native access violation
instead of raising a catchable `ImportError` when it can't find one. That crash happens at *import*
time, so it took down every test in the process, not just `UnstructuredParser`'s own. The standard
pip-installable Windows workaround, `python-magic-bin`, isn't a real fix: it installs its own
`magic/__init__.py` at the same path as `python-magic`'s, predates and lacks `compat.py` entirely,
and hasn't been released since 2017 -- pairing the two risks an install-order-dependent file
collision, not a working combination. So on Windows, `UnstructuredParser`'s tests exercise the
already-tested `OptionalDependencyError` fallback path (same mechanism as the "not installed" case
above), not real parsing -- `unstructured` genuinely isn't installed there, not simulated.

**A separate, real, opt-in integration profile also exists**, marked `pytest.mark.e2e` (excluded
from `-m "not e2e"`, the flag every documented full-suite command in this file and the root
`AGENTS.md` already passes -- and silently uncollected by `unittest discover` too, since both
files use plain pytest functions with fixtures rather than `TestCase` subclasses, matching the
existing `tests/ext/flask`/`tests/ext/workflow/durabletask` caveat):

- `test_pipeline_integration.py` -- a full `DurableRAGPipeline` run through a real `S3Source`
  (LocalStack), a real `PgVectorStore` (a `pgvector/pgvector` Postgres image), and a real Dapr
  Workflow sidecar, then a real query through `ActiveVersionResolver`. Three scenarios, each
  proving something distinct real infrastructure can catch that fakes can't:
  - `test_ingests_activates_and_is_queryable_end_to_end` -- the basic happy path.
  - `test_a_second_run_of_unchanged_content_skips_every_document` -- a full *second* run of an
    *already-completed* version skips re-embedding (`CompletionRecord`'s idempotency holding
    across independent runs).
  - `test_a_real_worker_process_crash_mid_run_resumes_from_where_it_left_off` -- the literal
    headline scenario: a real worker *process* (`_crash_resume_worker.py`, launched via
    `subprocess.Popen`, not simulated in-process) is hard-exited by `FailureInjector`
    (`os._exit(70)`) partway through a 10-document run, and a second, fresh worker process
    resumes the *same* Dapr Workflow instance and finishes it, with `embedding_requests`
    proving none of the pre-crash documents were re-embedded. Distinct from the "second run"
    test above: that one proves idempotency *across* independent runs; this one proves resuming
    *the same in-flight run*, which is what durabletask's own crash recovery actually is.
  - Fakes only the embedder and parser (a hash-based `DeterministicEmbedder`, a `.txt`-only
    `PlainTextParser`, both in `_rag_integration_fixtures.py`, shared with the subprocess
    worker), since OpenAI/`unstructured` wire compatibility is already covered elsewhere against
    mocks -- what this file proves is durability, not those two adapters' own logic.
- `test_sources_azure_blob_integration.py` -- `AzureBlobSource` against a real Azurite container.

Each file's module comment has the exact `docker run` commands and `uv run pytest ... -m e2e`
invocation. Building and running these surfaced two genuine bugs:

1. (`_activity_update_status`'s comment in `pipeline.py`): re-running a version's stable-instance-ID
   under a *different* explicit `instance_id` (an intentionally-supported `DurableRAGPipeline.start()`
   capability, not just the default resume-with-the-same-ID path) left `PipelineStatus` permanently
   attributed to whichever instance first wrote it, silently accumulating counts across independent
   runs instead of resetting for the new one -- invisible to every existing unit test because none of
   them exercised two full runs of one version under two different instance IDs against a real,
   persistent-across-calls state store.
2. A test-harness-only bug in `_spawn_crash_test_worker` (`test_pipeline_integration.py`), not in
   `dapr.ext.rag` itself: its original readiness check assumed a spawned worker's *first* stdout
   line was always its own `CRASH_TEST_WORKER_READY` marker, and on a mismatch called a plain
   blocking `.read()` to capture "the rest" for an error message. A worker process that starts
   successfully never closes stdout (it keeps running to serve work items), so that `.read()`
   call -- waiting for EOF that will never come -- hung forever the one time something else
   legitimately got printed first, with no timeout to save it. Fixed by reading output on a
   background thread into a queue the caller polls against a deadline, which cannot block past
   that deadline regardless of what the child process does. A `sample`/stack-trace of the stuck
   process (blocked in `_io_FileIO_readall_impl` -> `read`) is what found this, after the failure
   mode itself -- reproducible only when all three tests in the file ran together, not any pair
   of them -- ruled out both a one-off fluke and a `dapr.ext.rag` bug.

## Key details

- **`pipeline_id` defaults to `vector_store.target_index_name`** (the collection/index name) if
  not given explicitly, and namespaces every workflow/activity registration name
  (`rag_ingest__{pipeline_id}`, etc.) so multiple `DurableRAGPipeline` instances can share one
  process without name collisions.
- **Activities are plain closures, not bound methods, at registration time.** `WorkflowRuntime`
  registration (and `call_activity` given a function rather than a string) can stamp a
  `_dapr_alternate_name` attribute onto the registered callable; bound methods don't support
  arbitrary attribute assignment. `pipeline.py::_register_workflow_and_activities` registers plain
  nested-function closures that delegate to `self._activity_*`/`self._orchestrate_*`, and every
  `call_activity`/`schedule_new_workflow` call passes the activity/workflow's name as a string
  (which `DaprWorkflowContext` explicitly supports) rather than a function reference.
- **Provenance lives inside each vector's own metadata**, not a separate store: every
  `VectorRecord` written carries a full `ProvenanceRecord` (pipeline/workflow IDs, source
  identity, content/config hashes, parser/splitter/embedder identity, target index/version,
  timestamp, attempt number) merged into its metadata dict. This avoids a second per-chunk
  storage system and keeps provenance queryable alongside search results. No credentials, signed
  URLs, or connection strings are ever included (`Embedder.config()`/`DocumentParser.config()`
  implementations only return non-secret, behavior-affecting settings).
- **An empty manifest (zero discovered documents) fails validation on purpose** -- see
  `pipeline.py::_activity_validate_version`'s comment -- rather than trivially activating an empty
  index, which is far more likely to mean a misconfigured prefix/source than an intentional
  empty version.
- **`FailureInjector` (`testing.py`) is opt-in and off by default** (`None`/no-op unless a
  `DurableRAGPipeline` is explicitly constructed with `failure_injector=FailureInjector(...)`); it
  calls `os._exit()` (not `sys.exit()`) to simulate a real crash, deliberately skipping
  cleanup/atexit handling. Never wire this into a normal production code path.
- **`AzureOpenAIChatClient.generate_answer` (`generation.py`) is query-time only**, called from a
  retrieval-side process (e.g. `examples/rag/query_api.py`), never from the workflow -- generation
  needs the *question*, asked at query time, which doesn't exist during ingestion. It refuses to
  answer (a fixed insufficient-evidence response, no citations) when `matches` is empty, rather than
  letting the model guess without grounding.
- **`triggers.EventDeduplicator` and `SourceChangeEvent.event_id`** give event-driven ingestion
  (Event Grid/Service Bus for Azure, S3 event notifications for AWS) an idempotency key independent
  of the underlying pub/sub system's own delivery guarantees -- both systems document at-least-once
  delivery, so a duplicate/redelivered notification must not start a second workflow instance or
  re-ingest a document. `pubsub_trigger_servicebus.py`/`pubsub_trigger.py` check
  `already_seen(event_id)` before scheduling a workflow and `mark_seen(event_id)` after, backed by a
  Dapr state key with a TTL (not workflow state -- this check happens *before* a workflow instance
  exists).
