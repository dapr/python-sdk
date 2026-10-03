# Durable RAG ingestion example

A runnable sample for `DurableRAGPipeline`: discover documents from S3 or Azure Blob Storage,
parse and chunk them, embed them with OpenAI or Azure OpenAI, and write them into a versioned
pgvector, Pinecone, or Azure AI Search index -- surviving a worker crash mid-run without
re-embedding completed work, and never exposing a partially-built index to queries. See
[`docs/rag/README.md`](../../docs/rag/README.md) for the full architecture and configuration
reference this example is built on, and [`dapr/ext/rag/AGENTS.md`](../../dapr/ext/rag/AGENTS.md)
for internals.

All scripts here read their configuration from environment variables (`config.py`), so the same
files work across every supported combination -- see [`.env.example`](.env.example) for every
variable.

## Quickstart (fully local, except embeddings)

The fastest path to a working end-to-end run: LocalStack standing in for S3, a local Docker
Postgres for pgvector, and a real OpenAI API key for embeddings (the one piece with no local
emulator). Every command below is copy-pasteable, in order, from this directory.

1. **Initialize Dapr** (skip if you've already run this once):
   ```sh
   dapr init
   ```

2. **Start LocalStack (S3) and a local pgvector Postgres.** Port 5432 is Postgres's own default
   and is often already taken by a locally-installed Postgres -- 5544 avoids that:
   ```sh
   docker run -d --rm --name rag-localstack -p 4566:4566 -e SERVICES=s3 localstack/localstack:3
   docker run -d --rm --name rag-pgvector -p 5544:5432 \
       -e POSTGRES_PASSWORD=postgres -e POSTGRES_DB=ragdb pgvector/pgvector:pg16
   ```

3. **Install this example's dependencies**:
   ```sh
   pip3 install -r requirements.txt
   ```

4. **Configure**:
   ```sh
   cp .env.example .env
   ```
   Edit `.env` and set:
   - `OPENAI_API_KEY=<your real key>` -- the only real credential this quickstart needs.
   - `RAG_S3_ENDPOINT_URL=http://localhost:4566`
   - `RAG_PGVECTOR_CONNECTION_STRING=postgresql://postgres:postgres@localhost:5544/ragdb`

   Then load it, plus the two AWS variables LocalStack requires (any non-empty value works --
   `.env.example` notes this but doesn't template the lines, since real AWS deployments should
   never set them):
   ```sh
   export $(grep -v '^#' .env | xargs)
   export AWS_ACCESS_KEY_ID=test
   export AWS_SECRET_ACCESS_KEY=test
   ```

5. **Create the bucket and upload a sample document** (`boto3` is already installed from step 3):
   ```sh
   python3 -c "
   import boto3
   s3 = boto3.client('s3', endpoint_url='http://localhost:4566', region_name='us-east-1')
   s3.create_bucket(Bucket='company-docs')
   s3.put_object(Bucket='company-docs', Key='policies/remote-work.txt',
                 Body=b'Employees may work remotely up to three days per week.')
   "
   ```

6. **Start the worker** and leave it running in this terminal (watch for `Worker ready.`):
   ```sh
   dapr run --app-id rag-worker --resources-path components/ -- python3 worker.py
   ```

7. **In a second terminal**, first export the same variables again -- this is a new shell, so step
   4's exports aren't there:
   ```sh
   export $(grep -v '^#' .env | xargs)
   export AWS_ACCESS_KEY_ID=test
   export AWS_SECRET_ACCESS_KEY=test
   ```
   Skipping this fails fast, either with a clear `Missing required environment variable: ...`
   message or (for `OPENAI_API_KEY` specifically, which has no such check) a raw
   `openai.OpenAIError: Missing credentials` traceback -- neither is dangerous, just restart the
   command after exporting.

   Then start ingestion and poll status until it completes. Use the **same** `--app-id` as the
   worker (`rag-worker`), not a new one -- see "Running the worker and CLI" below for why that
   matters:
   ```sh
   dapr run --app-id rag-worker --resources-path components/ -- python3 cli.py start --version v1
   dapr run --app-id rag-worker --resources-path components/ -- python3 cli.py status --version v1
   ```
   Re-run `status` (a few seconds apart) until it shows `"stage": "completed"` and
   `"activation_succeeded": true`.

8. **Query it**:
   ```sh
   dapr run --app-id rag-worker --resources-path components/ -- python3 cli.py query "What is the remote work policy?"
   ```
   You should see `remote-work.txt` as the top-scoring match.

When you're done, stop the worker (`Ctrl+C` in its terminal) and the containers:
```sh
docker stop rag-localstack rag-pgvector
```

**Re-running this later?** Use a new `--version` (e.g. `v2`), not `v1` again. `cli.py start
--version v1` against a version that's already been used reattaches to that same, deterministic
workflow instance instead of starting a fresh one -- Dapr Workflow's state (kept in `dapr init`'s
Redis) isn't cleared by stopping the LocalStack/pgvector containers above, so you'd silently get
back the old run's status instead of processing anything new. This matches real usage anyway: a
version is meant to be unique per batch of content, not reused across attempts.

From here: "Failure and resume demo" below shows the crash/resume behavior on this exact setup
(just add the `RAG_DEMO_FAIL_AFTER_DOCUMENTS` trigger before restarting the worker); "Prerequisites"
and the sections after it are the general reference for the other source/embedder/vector-store
combinations (Azure Blob, Pinecone, Azure AI Search) and the Azure-native flagship path.

## Prerequisites

- [Dapr CLI and initialized environment](https://docs.dapr.io/getting-started)
- [Install Python 3.10+](https://www.python.org/downloads/)
- [Docker](https://docs.docker.com/get-docker/) -- only for the Quickstart's local LocalStack/
  pgvector containers; skip it if you're pointing at real cloud services directly.
- One source (an S3 bucket or Azure Blob container with a few documents), one embedder (an OpenAI
  or Azure OpenAI API key/deployment), and one vector store (a Postgres instance with the
  `pgvector` extension available, a Pinecone index, or an Azure AI Search service) -- see
  `docs/rag/README.md`'s per-provider configuration section for exactly what each needs.
  `docs/rag/README.md`'s "Local development with LocalStack and Azurite" section covers the source
  side for local testing without real cloud credentials.

### Install requirements

```sh
pip3 install -r requirements.txt
```

### Configure

```sh
cp .env.example .env
# edit .env with real values, then:
export $(grep -v '^#' .env | xargs)
```

**This export is per-shell, not global.** Every terminal you run `worker.py`, `cli.py`, or
`failure_demo.py` from needs it run again -- a fresh terminal that skips it fails fast, either with
a clear `Missing required environment variable: ...` message or (for `OPENAI_API_KEY`
specifically, which has no such check) a raw `openai.OpenAIError: Missing credentials` traceback.

## Running the worker and CLI

The worker and CLI are separate processes on purpose: the worker (`worker.py`) is the thing that
must keep running (or be restarted) for ingestion to make progress; the CLI (`cli.py`) is a
short-lived process that only schedules/queries runs through the Dapr sidecar. They must run with
the **same** `--app-id`, though -- not "each with its own" as you might expect from other
multi-process Dapr examples:

```sh
dapr run --app-id rag-worker --resources-path components/ -- python3 worker.py
```

In another terminal (export your `.env` variables there too -- see "Configure" above; it's a new
shell):

```sh
dapr run --app-id rag-worker --resources-path components/ -- python3 cli.py start --version 2026-09
dapr run --app-id rag-worker --resources-path components/ -- python3 cli.py status --version 2026-09
dapr run --app-id rag-worker --resources-path components/ -- python3 cli.py resolve
dapr run --app-id rag-worker --resources-path components/ -- python3 cli.py query "What is the remote work policy?"
```

**Why the same app-id:** Dapr Workflow is backed by Dapr Actors internally, and the actor type
that hosts a given app's workflows/activities is namespaced by that app's `--app-id`
(`dapr.internal.<namespace>.<app-id>.workflow`). `DaprWorkflowClient` -- what `cli.py`'s
`pipeline.start()`/`get_status()` and `failure_demo.py`'s polling loop use under the hood -- always
targets the actor type namespaced under its *own local* sidecar's app-id; it has no parameter to
target a different one (that only exists on `ctx.call_activity(..., app_id=...)`, for cross-app
calls made from inside an already-running workflow). Give the CLI a different app-id than the
worker and it doesn't error -- it **hangs forever**, because its sidecar waits on a placement-table
entry for an actor type that nothing will ever register. The CLI can still be a separate OS
process, restarted per invocation, even on a different machine -- it just needs that one string to
match the worker's.

`components/statestore.yaml` (a local Redis state store, with the `actorStateStore: "true"`
metadata Dapr Workflow requires) and `components/pubsub.yaml` (a local Redis pub/sub, standing in
for the real SNS/SQS/EventBridge or Azure Service Bus component -- see "Event-driven ingestion"
below) are provided for local development against `dapr init`'s default Redis. Point
`RAG_PGVECTOR_CONNECTION_STRING`/`RAG_PINECONE_INDEX`+`PINECONE_API_KEY`/`AZURE_SEARCH_ENDPOINT` at
a real service for the vector store side -- there's no local emulator for any of them.

## Failure and resume demo

Proves the core value proposition: a worker crash mid-run resumes without repeating completed
embedding work, and without exposing an incomplete index.

1. In one terminal, set a failure trigger and start the worker:
   ```sh
   export RAG_DEMO_FAIL_AFTER_DOCUMENTS=2
   dapr run --app-id rag-worker --resources-path components/ -- python3 worker.py
   ```
2. In another terminal (export your `.env` variables there too, plus the AWS test vars -- it's a
   new shell), start ingestion and watch status live. Both use the worker's **same** `--app-id`
   (see "Running the worker and CLI" above for why):
   ```sh
   dapr run --app-id rag-worker --resources-path components/ -- python3 cli.py start --version demo
   dapr run --app-id rag-worker --resources-path components/ -- python3 failure_demo.py --version demo
   ```
3. After the second document, the worker process hard-exits (`os._exit`, skipping cleanup --
   simulating a real crash or pod restart) -- you'll see the `dapr run` for `rag-worker` exit too.
4. Unset the trigger and restart the **same** worker:
   ```sh
   unset RAG_DEMO_FAIL_AFTER_DOCUMENTS
   dapr run --app-id rag-worker --resources-path components/ -- python3 worker.py
   ```
   Do **not** re-run `cli.py start` -- Dapr Workflow's own durability resumes the same orchestration
   instance automatically once the worker reconnects.
5. Watch `failure_demo.py`'s output (or run `cli.py status --version demo` again): the run reaches
   `stage=completed`, and `embedding_requests`/`avoided_embedding_units` show the documents
   processed before the crash were not re-embedded.

`RAG_DEMO_FAIL_AFTER_EMBEDDING_DOCUMENT=<document_id>` and `RAG_DEMO_FAIL_DURING_BATCH=<index>` are
the other two trigger points (see `.env.example`) -- set at most one at a time, and never in a
normal run; `FailureInjector` (`dapr/ext/rag/testing.py`) is off by default and only exists for
this kind of deliberate demonstration.

## Event-driven ingestion

One example subscriber per provider, entering through Dapr pub/sub rather than a direct
`cli.py start` call:

```sh
# S3: Blob change -> SNS/SQS or EventBridge -> Dapr pub/sub -> here
dapr run --app-id rag-s3-trigger --resources-path components/ --app-port 6001 -- python3 pubsub_trigger.py

# Azure: Blob change -> Event Grid -> Service Bus -> Dapr pub/sub -> here
dapr run --app-id rag-azure-trigger --resources-path components/azure/ --app-port 6002 -- python3 pubsub_trigger_servicebus.py
```

Both deduplicate by event ID (`EventDeduplicator`) and debounce a burst of changes into one
prefix-level reconciliation run (`reconciliation_workflow.py`) rather than starting ingestion per
individual event -- see that module's docstring and `docs/rag/README.md`'s "Event-driven ingestion"
section for why, and its documented limitation for a multi-replica subscriber deployment.

## The Azure-native flagship path

The complete path from the design brief:

```
Azure Blob Storage -> Event Grid -> Service Bus -> Dapr pub/sub -> Dapr Workflow
    -> Azure OpenAI embeddings -> versioned Azure AI Search index -> alias activation
    -> RAG query API -> Azure AI Search hybrid retrieval -> Azure OpenAI grounded answer + citations
```

Set `RAG_SOURCE=azure-blob`, `RAG_EMBEDDER=azure-openai`, `RAG_VECTOR_STORE=azure-ai-search`, plus
the corresponding `AZURE_*` variables (see `.env.example`), provision the Azure resources (see
[`infra/README.md`](infra/README.md) -- **not validated against a real subscription**, review
before use), and load `components/azure/*.yaml` instead of the local Redis components. Then:

1. Upload a few documents to the configured Blob container.
2. `cli.py start --version 2026-09` -- starts the indexing workflow.
3. `failure_demo.py --version 2026-09` -- observe document/chunk progress live.
4. Set `RAG_DEMO_FAIL_AFTER_EMBEDDING_DOCUMENT=<a document_id from the status output>` and restart
   the worker mid-run to intentionally terminate it during embedding (see "Failure and resume demo"
   above for the full pattern).
5. Restart the worker (trigger unset) -- completed batches are not embedded again.
6. Once `stage=completed` and `validation_succeeded=true`, activation (with
   `activate_when_complete=True`, the default) switches the Azure AI Search alias automatically --
   `cli.py resolve` shows the newly active version.
7. `python3 query_api.py "What is the remote work policy?"` -- submits a question.
8. Internally: retrieves via Azure AI Search hybrid search through the stable alias...
9. ...then calls Azure OpenAI to generate a grounded answer...
10. ...and prints the answer with citations back to the source blobs, plus `index_version` and
    `workflow_instance_id` for provenance:
    ```json
    {
      "answer": "...",
      "citations": [{"title": "employee-handbook.pdf", "source_uri": "...", "chunk_id": "...", "score": 0.91}],
      "index_version": "2026-09",
      "workflow_instance_id": null,
      "sufficient_evidence": true
    }
    ```

See [`docs/rag/observability.md`](../../docs/rag/observability.md) for the spans/correlation IDs
that let you trace one blob change through this entire path in Application Insights, and
[`docs/rag/azure-rbac.md`](../../docs/rag/azure-rbac.md) for exactly which identity needs which
permission at each step.

## Foundry IQ knowledge-source registration (optional)

Set `RAG_FOUNDRY_IQ_KNOWLEDGE_SOURCE` (plus `AZURE_SEARCH_SEMANTIC_CONFIG`, which it requires)
before starting `worker.py`, and every successful activation also registers/updates that Foundry
IQ knowledge source, pointed at the version's concrete physical index -- see
[`docs/rag/foundry-iq.md`](../../docs/rag/foundry-iq.md). Off by default; leave the variable
unset for every other flow above.

## What this example does not automate

There is no `tests/examples/test_rag.py`: every combination above needs a real (or LocalStack/
Azurite-backed) cloud source, a real or local vector store, and -- for the embedder and Azure AI
Search/OpenAI paths -- a real service with no local emulator, which the default test suite
deliberately avoids depending on (see `dapr/ext/rag/AGENTS.md`'s Testing section).

**What's actually been verified, manually, against real infrastructure:** the Quickstart above --
S3 via LocalStack, a real pgvector Postgres, and a real OpenAI key -- end to end, including
`start`/`status`/`resolve`/`query` all returning correct results, and the crash/resume behavior in
"Failure and resume demo" with a real worker process killed mid-run.

**What has not been run against anything real:** the Azure-native flagship path (Azure Blob, Azure
OpenAI, Azure AI Search, Foundry IQ -- `infra/README.md` says outright it's "not validated against
a real subscription"), the Pinecone vector store, and event-driven ingestion (both pub/sub
triggers). Those are exercised only by the mocked-I/O unit tests. Treat them as unverified until
you've run them yourself with real or local-emulated credentials.
