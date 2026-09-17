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

# Real, opt-in end-to-end test of DurableRAGPipeline against live infrastructure.
#
# Unlike every other file in this directory, this one does not mock or fake the source, the
# vector store, or the Dapr sidecar -- it runs a real ingestion through a real S3Source
# (against LocalStack), a real PgVectorStore (against a real PostgreSQL with the `vector`
# extension), and a real Dapr Workflow engine (a real `dapr run` sidecar), then queries the
# result back through ActiveVersionResolver. It only fakes the two adapters that would
# otherwise require a paid third-party API for a unittest-suite-level test: the embedder (a
# tiny deterministic hash-based one) and the parser (bytes decoded as one Document per file,
# skipping unstructured's real format detection). Both of those are already covered thoroughly
# by test_embedding_openai.py/test_embedding_azure_openai.py/test_parsing_unstructured.py
# against mocks -- what isn't covered anywhere else is "does a real Dapr Workflow, backed by a
# real vector store, actually discover, checkpoint, resume, validate, and activate a real run."
#
# Marked e2e (excluded from the default `-m "not e2e"` suite; see root AGENTS.md) and skips
# itself cleanly if its two prerequisites aren't reachable, rather than failing.
#
# Prerequisites (start once, independent of any single test run):
#
#   # 1. A local Dapr runtime and Redis (same prerequisite as tests/integration/):
#   dapr init
#
#   # 2. LocalStack (S3), on its default port:
#   docker run -d --rm --name rag-it-localstack -p 4566:4566 -e SERVICES=s3 \
#       localstack/localstack:3
#
#   # 3. PostgreSQL with the pgvector extension pre-installed:
#   docker run -d --rm --name rag-it-pgvector -p 5544:5432 \
#       -e POSTGRES_PASSWORD=postgres -e POSTGRES_DB=ragtest pgvector/pgvector:pg16
#
# Then:
#
#   uv run pytest tests/ext/rag/test_pipeline_integration.py -m e2e -v
#
# Override RAG_IT_S3_ENDPOINT / RAG_IT_PG_DSN if either service isn't at the default address.
# Each test run uses a fresh, randomly-suffixed bucket/collection name, and tears both down
# afterward -- the containers themselves are not managed by this file (matching how
# tests/integration/ treats dapr_redis as an externally-provisioned prerequisite, not
# something the suite starts itself).
#
# Two different kinds of "crash and resume" are tested here, deliberately not conflated:
#
# - test_a_real_worker_process_crash_mid_run_resumes_from_where_it_left_off spawns the actual
#   worker as a *separate OS process* (_crash_resume_worker.py, via subprocess.Popen) so
#   FailureInjector's real os._exit() can kill it for real without taking pytest down too, then
#   starts a second, fresh worker process and confirms the *same* Dapr Workflow instance
#   resumes on its own -- the literal scenario this pipeline exists for.
# - test_a_second_run_of_unchanged_content_skips_every_document instead starts a full *second*
#   run of an *already-completed* version and confirms it skips re-embedding -- a different
#   (also real, also valuable) proof: that CompletionRecord's idempotency holds across
#   independent runs, not only within one resumed instance.

from __future__ import annotations

import os
import queue
import subprocess
import sys
import threading
import time
import uuid
from contextlib import contextmanager
from pathlib import Path

import httpx
import pytest

from dapr.clients import DaprClient
from dapr.ext.rag.models import PipelineConfig
from dapr.ext.rag.pipeline import DurableRAGPipeline
from dapr.ext.rag.retrieval import ActiveVersionResolver
from dapr.ext.rag.sources.s3 import S3Source
from dapr.ext.rag.splitting import TextSplitter
from dapr.ext.rag.vector_stores.pgvector import PgVectorStore
from tests.ext.rag._rag_integration_fixtures import DeterministicEmbedder, PlainTextParser
from tests.integration.conftest import DaprTestEnvironment
from tests.wait_utils import wait_until

pytestmark = pytest.mark.e2e

HOST = '127.0.0.1'
GRPC_PORT = 13701
HTTP_PORT = 3700
INTERNAL_GRPC_PORT = 13702
METRICS_PORT = 9071

S3_ENDPOINT = os.environ.get('RAG_IT_S3_ENDPOINT', 'http://127.0.0.1:4566')
PG_DSN = os.environ.get('RAG_IT_PG_DSN', 'postgresql://postgres:postgres@127.0.0.1:5544/ragtest')

RESOURCES_DIR = Path(__file__).resolve().parent / 'integration_resources'
REPO_ROOT = Path(__file__).resolve().parents[3]
INGEST_TIMEOUT_SECONDS = 60.0


@pytest.fixture(scope='module')
def s3_client():
    """A boto3 S3 client against LocalStack, or a clean `pytest.skip` if unreachable."""
    try:
        import boto3
    except ImportError:
        pytest.skip('boto3 is not installed (needed for both S3Source and this fixture)')

    try:
        httpx.get(S3_ENDPOINT, timeout=2.0)
    except httpx.HTTPError as exc:
        pytest.skip(f'LocalStack not reachable at {S3_ENDPOINT} ({exc}) -- see module docstring')

    return boto3.client(
        's3',
        endpoint_url=S3_ENDPOINT,
        region_name='us-east-1',
        aws_access_key_id='test',
        aws_secret_access_key='test',
    )


@pytest.fixture(scope='module')
def pg_dsn():
    """The pgvector Postgres DSN, or a clean `pytest.skip` if unreachable."""
    try:
        import psycopg
    except ImportError:
        pytest.skip('psycopg is not installed (needed for both PgVectorStore and this fixture)')

    try:
        with psycopg.connect(PG_DSN, connect_timeout=2):
            pass
    except Exception as exc:
        pytest.skip(f'pgvector Postgres not reachable at {PG_DSN} ({exc}) -- see module docstring')

    return PG_DSN


@pytest.fixture(scope='module')
def dapr_env():
    env = DaprTestEnvironment(default_resources=RESOURCES_DIR)
    yield env
    env.cleanup()


@pytest.fixture(scope='module')
def sidecar(dapr_env):
    return dapr_env.start_sidecar(
        app_id='test-rag-pipeline-integration',
        grpc_port=GRPC_PORT,
        http_port=HTTP_PORT,
        internal_grpc_port=INTERNAL_GRPC_PORT,
        metrics_port=METRICS_PORT,
    )


@pytest.fixture()
def bucket(s3_client):
    name = f'rag-it-{uuid.uuid4().hex[:12]}'
    s3_client.create_bucket(Bucket=name)
    yield name
    objects = s3_client.list_objects_v2(Bucket=name).get('Contents', [])
    if objects:
        s3_client.delete_objects(
            Bucket=name, Delete={'Objects': [{'Key': o['Key']} for o in objects]}
        )
    s3_client.delete_bucket(Bucket=name)


@pytest.fixture()
def collection():
    return f'rag_it_{uuid.uuid4().hex[:12]}'


@pytest.fixture()
def pipeline(sidecar, bucket, collection, pg_dsn):
    from dapr.ext.workflow import DaprWorkflowClient, WorkflowRuntime

    # Constructed explicitly (rather than left for DurableRAGPipeline to own) so this fixture
    # can point them at `sidecar`'s ports -- which also means `pipeline.close()` won't close
    # them (it only closes clients it created itself), so this fixture closes them itself too.
    workflow_client = DaprWorkflowClient(host=HOST, port=str(GRPC_PORT))
    dapr_client = DaprClient(address=f'{HOST}:{GRPC_PORT}')

    pipeline = DurableRAGPipeline(
        source=S3Source(
            bucket=bucket,
            region_name='us-east-1',
            endpoint_url=S3_ENDPOINT,
            aws_access_key_id='test',
            aws_secret_access_key='test',
        ),
        parser=PlainTextParser(),
        splitter=TextSplitter(chunk_size=200, chunk_overlap=20),
        embedder=DeterministicEmbedder(),
        vector_store=PgVectorStore(connection_string=pg_dsn, collection=collection),
        state_store_name='statestore',
        pipeline_id=collection,
        config=PipelineConfig(
            max_concurrent_documents=4, embedding_batch_size=8, manifest_page_size=50
        ),
        workflow_runtime=WorkflowRuntime(host=HOST, port=str(GRPC_PORT)),
        workflow_client=workflow_client,
        dapr_client=dapr_client,
    )
    pipeline.run_worker()
    yield pipeline
    pipeline.shutdown_worker()
    pipeline.close()
    workflow_client.close()
    dapr_client.close()


@pytest.fixture()
def pipeline_client(sidecar, bucket, collection, pg_dsn):
    """A `DurableRAGPipeline` that only ever acts as a *client* (`start`/`get_status`/
    `resolve_active_version`) -- unlike `pipeline` above, `run_worker()` is never called on
    this one, so it never executes any activity itself. Used by the real crash/resume test,
    where the actual worker(s) run as separate OS processes (`_crash_resume_worker.py`) --
    registering workflows/activities on this instance's own `WorkflowRuntime` is harmless
    bookkeeping as long as it's never started, matching how a short-lived CLI process is safe
    to construct without a live sidecar per `DurableRAGPipeline.run_worker`'s own docstring.
    """
    from dapr.ext.workflow import DaprWorkflowClient, WorkflowRuntime

    workflow_client = DaprWorkflowClient(host=HOST, port=str(GRPC_PORT))
    dapr_client = DaprClient(address=f'{HOST}:{GRPC_PORT}')

    client = DurableRAGPipeline(
        source=S3Source(
            bucket=bucket,
            region_name='us-east-1',
            endpoint_url=S3_ENDPOINT,
            aws_access_key_id='test',
            aws_secret_access_key='test',
        ),
        parser=PlainTextParser(),
        splitter=TextSplitter(chunk_size=200, chunk_overlap=20),
        embedder=DeterministicEmbedder(),
        vector_store=PgVectorStore(connection_string=pg_dsn, collection=collection),
        state_store_name='statestore',
        pipeline_id=collection,
        config=PipelineConfig(max_concurrent_documents=1),
        workflow_runtime=WorkflowRuntime(host=HOST, port=str(GRPC_PORT)),
        workflow_client=workflow_client,
        dapr_client=dapr_client,
    )
    yield client
    client.close()
    workflow_client.close()
    dapr_client.close()


@pytest.fixture()
def crash_test_workers():
    """Tracks every worker subprocess a test spawns and force-terminates any still running at
    teardown, so a failed assertion mid-test never leaks an orphaned process holding the
    sidecar connection or S3/pgvector connections open."""
    procs: list[subprocess.Popen] = []
    yield procs
    for proc in procs:
        if proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait(timeout=10)


READY_TIMEOUT_SECONDS = 30.0


def _spawn_crash_test_worker(
    *, bucket: str, collection: str, pg_dsn: str, fail_after_documents: int | None = None
) -> subprocess.Popen:
    """Starts `_crash_resume_worker.py` as a real, separate OS process and blocks until it
    reports readiness -- or raises, with whatever output it produced, if it exits or simply
    never reports readiness within `READY_TIMEOUT_SECONDS`.

    Output is read on a background thread into a queue the caller polls with a deadline,
    deliberately never a plain blocking `.readline()`/`.read()` on the calling thread: a worker
    that starts successfully never closes its stdout (it keeps running to serve work items), so
    treating "the first line wasn't the ready marker" as "read the rest of the output to see
    why" would block forever once that assumption is wrong -- which it was, once, during this
    test's development (real Dapr SDK log output can legitimately precede the ready marker).
    Polling a queue against a deadline instead can never block past `READY_TIMEOUT_SECONDS`, no
    matter what the child process does.
    """
    env = dict(os.environ)
    env['RAG_CRASH_TEST_GRPC_PORT'] = str(GRPC_PORT)
    env['RAG_CRASH_TEST_HTTP_PORT'] = str(HTTP_PORT)
    env['RAG_CRASH_TEST_BUCKET'] = bucket
    env['RAG_CRASH_TEST_COLLECTION'] = collection
    env['RAG_CRASH_TEST_S3_ENDPOINT'] = S3_ENDPOINT
    env['RAG_CRASH_TEST_PG_DSN'] = pg_dsn
    if fail_after_documents is not None:
        env['RAG_CRASH_TEST_FAIL_AFTER_DOCUMENTS'] = str(fail_after_documents)
    else:
        env.pop('RAG_CRASH_TEST_FAIL_AFTER_DOCUMENTS', None)

    proc = subprocess.Popen(
        [sys.executable, '-m', 'tests.ext.rag._crash_resume_worker'],
        cwd=str(REPO_ROOT),
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )

    output_lines: queue.Queue[str | None] = queue.Queue()

    def _pump_output() -> None:
        assert proc.stdout is not None
        for line in proc.stdout:
            output_lines.put(line)
        output_lines.put(None)  # sentinel: stdout closed, i.e. the process exited

    threading.Thread(target=_pump_output, daemon=True).start()

    seen: list[str] = []
    deadline = time.monotonic() + READY_TIMEOUT_SECONDS
    while time.monotonic() < deadline:
        try:
            line = output_lines.get(timeout=0.5)
        except queue.Empty:
            continue
        if line is None:
            break  # stdout closed -- the process exited before ever reporting readiness
        seen.append(line)
        if 'CRASH_TEST_WORKER_READY' in line:
            return proc

    if proc.poll() is None:
        proc.kill()
    proc.wait(timeout=10)
    raise RuntimeError(
        f'crash-test worker (pid={proc.pid}) never reported readiness within '
        f'{READY_TIMEOUT_SECONDS}s; output captured so far:\n{"".join(seen)}'
    )


def _put_text_object(s3_client, bucket: str, key: str, text: str) -> None:
    s3_client.put_object(
        Bucket=bucket, Key=key, Body=text.encode('utf-8'), ContentType='text/plain'
    )


def _wait_for_terminal_status(pipeline: DurableRAGPipeline, version: str, *, instance_id: str):
    """Polls `get_status(version)` for `instance_id`'s own terminal status.

    `PipelineStatus` is keyed by `(pipeline_id, version)`, not by instance ID -- filtering on
    `workflow_instance_id` matters whenever a version is run more than once (e.g. the
    already-completed status a prior run left behind), or `wait_until` would return
    immediately on stale state instead of waiting for *this* run.
    """

    def poll():
        status = pipeline.get_status(version)
        is_this_run = status is not None and status.workflow_instance_id == instance_id
        return status if is_this_run and status.stage in ('completed', 'failed') else None

    return wait_until(poll, timeout=INGEST_TIMEOUT_SECONDS)


@contextmanager
def _resolver_for(collection: str, pg_dsn: str):
    # A fresh vector_store/embedder rather than reaching into `pipeline`'s: both are cheap to
    # construct and this is exactly how a separate retrieval-side process would do it in
    # practice (see docs/rag/README.md's "Starting, observing, and querying a pipeline").
    # A local DaprClient, closed here explicitly: ActiveVersionResolver.close() only closes a
    # DaprClient it created itself, not one passed in (same ownership rule as PgVectorStore's
    # connection_factory and DurableRAGPipeline's own workflow_client/dapr_client params).
    dapr_client = DaprClient(address=f'{HOST}:{GRPC_PORT}')
    resolver = ActiveVersionResolver(
        pipeline_id=collection,
        state_store_name='statestore',
        vector_store=PgVectorStore(connection_string=pg_dsn, collection=collection),
        embedder=DeterministicEmbedder(),
        dapr_client=dapr_client,
    )
    try:
        yield resolver
    finally:
        resolver.close()
        dapr_client.close()


# Plain functions, not a unittest.TestCase: these need pytest fixtures (`bucket`, `pipeline`,
# ...) as parameters, which unittest.TestCase's setUp-based model cannot request. Matches
# `tests/integration/test_workflow_stateful_history.py`'s plain-function + fixture style.


def test_ingests_activates_and_is_queryable_end_to_end(
    s3_client, bucket, collection, pg_dsn, pipeline
):
    _put_text_object(
        s3_client,
        bucket,
        'policies/remote-work.txt',
        'Employees may work remotely three days per week.',
    )
    _put_text_object(
        s3_client,
        bucket,
        'policies/expenses.txt',
        'Travel expenses must be submitted within 30 days.',
    )

    instance_id = pipeline.start(version='v1')
    status = _wait_for_terminal_status(pipeline, 'v1', instance_id=instance_id)

    assert status.stage == 'completed', status
    assert status.completed_documents == 2
    assert status.failed_documents == 0
    assert status.activation_succeeded is True
    assert pipeline.resolve_active_version() == 'v1'

    with _resolver_for(collection, pg_dsn) as resolver:
        matches = resolver.query('remote work policy', top_k=5)

    assert matches, 'expected at least one match from the real pgvector query'
    best = matches[0]
    assert 'remote' in best.content.lower()
    assert best.metadata['pipeline_id'] == collection
    assert best.metadata['workflow_instance_id'] == instance_id
    assert best.metadata['source_provider'] == 's3'
    assert best.metadata['embedding_model'] == 'deterministic-test-embedder-v1'
    assert best.metadata['target_version'] == 'v1'


def test_a_second_run_of_unchanged_content_skips_every_document(
    s3_client, bucket, collection, pipeline
):
    """Proves the same `CompletionRecord` short-circuit that makes a real crash-and-restart
    avoid re-embedding -- see the module docstring for why this stands in for a literal
    process kill here."""
    _put_text_object(
        s3_client, bucket, 'policies/pto.txt', 'Unused PTO does not roll over into the next year.'
    )

    first_instance_id = pipeline.start(version='v1')
    first_status = _wait_for_terminal_status(pipeline, 'v1', instance_id=first_instance_id)
    assert first_status.stage == 'completed'
    assert first_status.embedded_chunks > 0

    second_instance_id = pipeline.start(version='v1', instance_id=f'{collection}-v1-rerun')
    assert second_instance_id != first_instance_id
    second_status = _wait_for_terminal_status(pipeline, 'v1', instance_id=second_instance_id)

    assert second_status.stage == 'completed'
    # A document whose content is unchanged is reported as *skipped*, not completed -- it did no
    # new work (see DocumentOutcomeStatus and _activity_update_status's counting).
    assert second_status.skipped_documents == 1, second_status
    assert second_status.completed_documents == 0, second_status
    assert second_status.embedded_chunks == 0, 'unchanged content must not be re-embedded'
    assert second_status.reused_chunks > 0, (
        f'a re-run of unchanged content must reuse prior work: {second_status}'
    )
    assert second_status.avoided_embedding_units > 0, second_status


def test_a_real_worker_process_crash_mid_run_resumes_from_where_it_left_off(
    s3_client, bucket, collection, pg_dsn, pipeline_client, crash_test_workers
):
    """The literal scenario `DurableRAGPipeline` exists for: a worker process is killed
    partway through a run, and a newly started worker process resumes the *same* in-flight
    Dapr Workflow instance, finishing only the documents that were not yet durably completed --
    not "a fresh run of already-completed work skips redoing it" (the test above), but "a run
    that was interrupted mid-flight continues from exactly where it stopped."

    Ten single-chunk documents; a real worker process configured to hard-exit (os._exit(70),
    via FailureInjector) once it starts a 10th document -- i.e. after 9 have already completed.
    max_concurrent_documents=1 (see _crash_resume_worker.py) makes this deterministic: documents
    are processed strictly one at a time, so "9 completed, crash starting the 10th" is exact,
    not a race between concurrently-running activities.
    """
    total_documents = 10
    crash_after = 9
    for i in range(total_documents):
        _put_text_object(
            s3_client, bucket, f'policies/doc-{i}.txt', f'unique content for document number {i}'
        )

    crashing_worker = _spawn_crash_test_worker(
        bucket=bucket, collection=collection, pg_dsn=pg_dsn, fail_after_documents=crash_after
    )
    crash_test_workers.append(crashing_worker)

    # A separate client connection starts the run -- the worker above executes it.
    instance_id = pipeline_client.start(version='v1')

    exit_code = crashing_worker.wait(timeout=INGEST_TIMEOUT_SECONDS)
    assert exit_code == 70, f'expected FailureInjector to hard-exit(70); got {exit_code}'

    # Real, partial progress landed durably *before* the crash -- exactly `crash_after`
    # documents, no more (deterministic: see the docstring above).
    partial_status = pipeline_client.get_status('v1')
    assert partial_status is not None
    assert partial_status.workflow_instance_id == instance_id
    assert partial_status.stage != 'completed', 'the run must still be in-flight, not finished'
    assert partial_status.completed_documents == crash_after, partial_status
    assert partial_status.embedding_requests == crash_after, partial_status

    # A second, fresh worker process -- no failure injector -- reconnects. Deliberately does
    # NOT call pipeline_client.start() again: per DurableRAGPipeline.start()'s own docstring,
    # reconnecting a worker to a still-running instance is what resumes it; re-scheduling is
    # neither needed nor correct while the instance is still non-terminal.
    resumed_worker = _spawn_crash_test_worker(bucket=bucket, collection=collection, pg_dsn=pg_dsn)
    crash_test_workers.append(resumed_worker)

    final_status = _wait_for_terminal_status(pipeline_client, 'v1', instance_id=instance_id)

    assert final_status.stage == 'completed', final_status
    assert final_status.failed_documents == 0, final_status
    assert final_status.completed_documents == total_documents, final_status
    # The strongest proof that documents 1-9 were never touched again: exactly one embedding
    # batch per document (one chunk each) across *both* worker processes combined -- if any of
    # the pre-crash documents had been silently re-embedded after the restart, this would be
    # greater than total_documents.
    assert final_status.embedding_requests == total_documents, final_status

    # Looked up by exact source_document_id, not text similarity: DeterministicEmbedder hashes
    # text into a vector with no semantic relationship to content (unlike a real embedder), so
    # asking "which of these 10 near-identical documents is closest to this query" would not
    # reliably pick the right one -- an exact metadata match is the correct tool here, and
    # confirms each document's own content really did land in pgvector, not just the count.
    with _resolver_for(collection, pg_dsn) as resolver:
        for i in range(total_documents):
            document_id = f's3://{bucket}/policies/doc-{i}.txt'
            [match] = resolver.query(
                'irrelevant -- filtered by document id below',
                top_k=1,
                metadata_filter={'source_document_id': document_id},
            )
            assert match.content == f'unique content for document number {i}'

    resumed_worker.terminate()
    resumed_worker.wait(timeout=10)
