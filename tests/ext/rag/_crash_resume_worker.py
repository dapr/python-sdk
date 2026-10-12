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

# A standalone worker *process* for test_pipeline_integration.py's real crash/resume test.
# Launched via `python -m tests.ext.rag._crash_resume_worker` (not imported) so that
# FailureInjector's real os._exit() kills only this process, never the pytest process driving
# the test -- proving an actual separate-process crash-and-restart, not a simulated one. No
# test_ prefix (not collected by pytest as a test module itself).
#
# Configuration comes entirely from environment variables, mirroring examples/rag/worker.py's
# own env-var-driven pattern (this is that same idea, scoped to exactly what the test needs).

from __future__ import annotations

import os
import signal
import sys
import threading

from dapr.clients import DaprClient
from dapr.conf import settings
from dapr.ext.rag.models import PipelineConfig
from dapr.ext.rag.pipeline import DurableRAGPipeline
from dapr.ext.rag.sources.s3 import S3Source
from dapr.ext.rag.splitting import TextSplitter
from dapr.ext.rag.testing import FailureInjector
from dapr.ext.rag.vector_stores.pgvector import PgVectorStore
from dapr.ext.workflow import DaprWorkflowClient, WorkflowRuntime
from tests.ext.rag._rag_integration_fixtures import DeterministicEmbedder, PlainTextParser

HOST = '127.0.0.1'


def _env(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise SystemExit(f'{name} must be set (see test_pipeline_integration.py)')
    return value


def main() -> None:
    grpc_port = _env('RAG_CRASH_TEST_GRPC_PORT')
    fail_after_documents = os.environ.get('RAG_CRASH_TEST_FAIL_AFTER_DOCUMENTS')
    collection = _env('RAG_CRASH_TEST_COLLECTION')

    # DaprClient's constructor blocks on an HTTP health check against
    # settings.DAPR_HTTP_PORT, which defaults to 3500 and is process-local -- this process
    # doesn't inherit the parent test process's own mutation of it (see
    # tests/integration/conftest.py's DaprTestEnvironment.start_sidecar for the same fix
    # applied there), so it must be set here too, before constructing DaprClient below.
    settings.DAPR_HTTP_PORT = int(_env('RAG_CRASH_TEST_HTTP_PORT'))

    pipeline = DurableRAGPipeline(
        source=S3Source(
            bucket=_env('RAG_CRASH_TEST_BUCKET'),
            region_name='us-east-1',
            endpoint_url=_env('RAG_CRASH_TEST_S3_ENDPOINT'),
            aws_access_key_id='test',
            aws_secret_access_key='test',
        ),
        parser=PlainTextParser(),
        splitter=TextSplitter(chunk_size=200, chunk_overlap=20),
        embedder=DeterministicEmbedder(),
        vector_store=PgVectorStore(
            connection_string=_env('RAG_CRASH_TEST_PG_DSN'), collection=collection
        ),
        state_store_name='statestore',
        pipeline_id=collection,
        # One document per batch: makes crash timing deterministic (fail_after_documents=N
        # crashes only once N documents have each individually completed their own
        # continue_as_new generation, never mid-way through a bigger concurrent batch).
        config=PipelineConfig(max_concurrent_documents=1),
        workflow_runtime=WorkflowRuntime(host=HOST, port=grpc_port),
        workflow_client=DaprWorkflowClient(host=HOST, port=grpc_port),
        dapr_client=DaprClient(address=f'{HOST}:{grpc_port}'),
        failure_injector=(
            FailureInjector(fail_after_documents=int(fail_after_documents))
            if fail_after_documents
            else None
        ),
    )
    pipeline.run_worker()
    print('CRASH_TEST_WORKER_READY', flush=True)

    stop = threading.Event()
    signal.signal(signal.SIGTERM, lambda *_args: stop.set())
    stop.wait()
    pipeline.shutdown_worker()
    pipeline.close()


if __name__ == '__main__':
    sys.exit(main() or 0)
