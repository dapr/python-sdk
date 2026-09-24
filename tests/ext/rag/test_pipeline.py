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

import dataclasses
import unittest
from datetime import datetime, timezone
from types import SimpleNamespace
from typing import Optional
from unittest import mock

import grpc

from dapr.ext.rag._wire import to_wire
from dapr.ext.rag.embedding.base import Embedder
from dapr.ext.rag.errors import DocumentParseError, TransientEmbeddingError
from dapr.ext.rag.models import (
    Chunk,
    Document,
    DocumentOutcomeStatus,
    DocumentWorkItem,
    EmbeddingBatchResult,
    FoundryIQKnowledgeSourceConfig,
    PipelineConfig,
    PipelineStage,
    SourceDocument,
    SourceMetadata,
    SourceProvider,
    UpsertResult,
    ValidationResult,
)
from dapr.ext.rag.parsing.base import DocumentParser
from dapr.ext.rag.pipeline import DurableRAGPipeline, _ActivationState, _IngestionState
from dapr.ext.rag.sources.base import DocumentSource
from dapr.ext.rag.splitting import DocumentSplitter
from dapr.ext.rag.vector_stores.base import VectorIndex

_SECRET_CONNECTION_STRING = 'postgresql://user:sk-should-not-leak@host/db'
_SECRET_API_KEY = 'sk-should-not-leak-either'


# ---------------------------------------------------------------------------
# Fakes: real (if minimal) ABC implementations with controllable behavior,
# rather than loose Mocks -- exercising this package's actual glue code
# (config()/config_fingerprint(), provenance construction) for real.
# ---------------------------------------------------------------------------


class _FakeSource(DocumentSource):
    def __init__(self, documents=(), content_by_id=None, metadata_sequence_by_id=None):
        self._documents = list(documents)
        self._content_by_id = content_by_id or {}
        self._metadata_sequence_by_id = metadata_sequence_by_id or {}
        self._metadata_call_count: dict[str, int] = {}
        self.closed = False

    @property
    def provider(self):
        return SourceProvider.S3

    def list_documents(self, prefix=None):
        return iter(self._documents)

    def get_document(self, document_id):
        return self._content_by_id[document_id]

    def get_metadata(self, document_id):
        sequence = self._metadata_sequence_by_id.get(document_id)
        if sequence is None:
            return SourceMetadata()
        call_index = self._metadata_call_count.get(document_id, 0)
        self._metadata_call_count[document_id] = call_index + 1
        return sequence[min(call_index, len(sequence) - 1)]

    def close(self):
        self.closed = True


class _FakeParser(DocumentParser):
    """Splits raw bytes on '||' into one Document per resulting piece."""

    def __init__(self, fail_for_document_ids=()):
        self._fail_for_document_ids = set(fail_for_document_ids)

    @property
    def parser_type(self):
        return 'fake-parser'

    def parse(self, content, document):
        if document.document_id in self._fail_for_document_ids:
            raise DocumentParseError(f'simulated parse failure for {document.document_id}')
        return [Document(page_content=piece) for piece in content.decode('utf-8').split('||')]


class _FakeSplitter(DocumentSplitter):
    """Splits a Document's page_content on '|' into one Chunk per piece."""

    @property
    def splitter_type(self):
        return 'fake-splitter'

    def split(self, document):
        pieces = [p for p in document.page_content.split('|') if p]
        return [
            Chunk(chunk_ordinal=i, content=p, metadata=dict(document.metadata))
            for i, p in enumerate(pieces)
        ]


class _FakeEmbedder(Embedder):
    def __init__(self, dimension=2, fail_on_texts=()):
        self._dimension = dimension
        self._fail_on_texts = set(fail_on_texts)
        self.calls: list[list[str]] = []

    @property
    def embedding_model(self):
        return 'fake-embedding-model'

    def config(self):
        return {
            'model': self.embedding_model,
            'api_key': _SECRET_API_KEY,
        }  # must never leak -- see config()

    def embed_batch(self, texts):
        self.calls.append(list(texts))
        for text in texts:
            if text in self._fail_on_texts:
                raise TransientEmbeddingError(f'simulated embedding failure for {text!r}')
        embeddings = [[float(i)] * self._dimension for i in range(len(texts))]
        return EmbeddingBatchResult(embeddings=embeddings, total_tokens=len(texts))


class _FakeVectorStore(VectorIndex):
    def __init__(self, index_name='company-knowledge'):
        self._index_name = index_name
        self.upserted: list[tuple] = []  # (version, VectorRecord)
        self.deleted: list[tuple] = []
        self.activate_version_calls: list[tuple] = []  # (version, previous_version)
        self.foundry_iq_registration_calls: list[dict] = []
        self.foundry_iq_registration_error: Optional[Exception] = None

    def activate_version(self, version, *, previous_version):
        self.activate_version_calls.append((version, previous_version))

    def register_foundry_iq_knowledge_source(
        self, version, *, name, description=None, source_data_fields=None, search_fields=None
    ):
        self.foundry_iq_registration_calls.append(
            {
                'version': version,
                'name': name,
                'description': description,
                'source_data_fields': source_data_fields,
                'search_fields': search_fields,
            }
        )
        if self.foundry_iq_registration_error is not None:
            raise self.foundry_iq_registration_error

    @property
    def target_index_name(self):
        return self._index_name

    @property
    def store_type(self):
        return 'fake-store'

    def upsert(self, records, version):
        records = list(records)
        self.upserted.extend((version, r) for r in records)
        return UpsertResult(upserted_count=len(records), version=version)

    def delete_document(self, document_id, version):
        self.deleted.append((version, document_id))

    def validate_version(self, version):
        chunks = [r for v, r in self.upserted if v == version]
        return ValidationResult(
            valid=len(chunks) > 0,
            version=version,
            actual_chunk_count=len(chunks),
            actual_document_count=len({c.document_id for c in chunks}),
        )

    def query(self, embedding, version, *, top_k=5, metadata_filter=None, query_text=None):
        return []


class _FakeSimpleVectorStore(VectorIndex):
    """A minimal `VectorIndex` with no `register_foundry_iq_knowledge_source` method at
    all -- unlike `_FakeVectorStore`, which every other fake in this file uses and which
    always has one. Used only to prove `DurableRAGPipeline`'s constructor validation
    actually rejects a vector_store that lacks the capability (a class attribute set to
    `None` would still satisfy `hasattr`, so this has to be a genuinely different class,
    not `_FakeVectorStore` with the method overridden away)."""

    @property
    def target_index_name(self):
        return 'company-knowledge'

    @property
    def store_type(self):
        return 'fake-simple-store'

    def upsert(self, records, version):
        return UpsertResult(upserted_count=len(list(records)), version=version)

    def delete_document(self, document_id, version):
        pass

    def validate_version(self, version):
        return ValidationResult(valid=True, version=version, actual_chunk_count=0)

    def query(self, embedding, version, *, top_k=5, metadata_filter=None, query_text=None):
        return []


class _FakeAbortedError(grpc.RpcError):
    def code(self):
        return grpc.StatusCode.ABORTED

    def details(self):
        return 'etag mismatch'


class _FakeDaprClient:
    """A minimal but *real* key-value store behind the DaprClient state API,
    including etag-conditional writes -- see dapr/clients/grpc/_state.py for
    the contract this mimics.
    """

    def __init__(self):
        self._store: dict[str, tuple[bytes, str]] = {}
        self._etag_counter = 0
        self.published_events = []

    def get_state(self, store_name, key, state_metadata=None, metadata=None):
        data, etag = self._store.get(key, (b'', ''))
        return SimpleNamespace(data=data, etag=etag)

    def save_state(
        self, store_name, key, value, etag=None, options=None, state_metadata=None, metadata=None
    ):
        _current_data, current_etag = self._store.get(key, (b'', ''))
        if etag and etag != current_etag:
            raise _FakeAbortedError()
        self._etag_counter += 1
        data = value.encode('utf-8') if isinstance(value, str) else value
        self._store[key] = (data, str(self._etag_counter))

    def publish_event(self, pubsub_name, topic_name, data, data_content_type=None):
        self.published_events.append(
            {'pubsub_name': pubsub_name, 'topic_name': topic_name, 'data': data}
        )

    def close(self):
        pass


class _PendingCall:
    def __init__(self, activity_name, input):
        self.activity_name = activity_name
        self.input = input


class _FakeWorkflowContext:
    def __init__(self, instance_id='wf-instance-1'):
        self.instance_id = instance_id
        self.is_replaying = False
        self.current_utc_datetime = datetime(2026, 9, 10, tzinfo=timezone.utc)
        self.calls: list[_PendingCall] = []
        self.continue_as_new_input = None

    def call_activity(
        self, activity, *, input=None, retry_policy=None, app_id=None, propagation=None
    ):
        pending = _PendingCall(activity_name=activity, input=input)
        self.calls.append(pending)
        return pending

    def continue_as_new(self, new_input, *, save_events=False):
        self.continue_as_new_input = new_input


def _activity_dispatch(pipeline):
    return {
        pipeline._activity_names['discover_and_manifest']: pipeline._activity_discover_and_manifest,
        pipeline._activity_names['get_manifest_batch']: pipeline._activity_get_manifest_batch,
        pipeline._activity_names['process_document']: pipeline._activity_process_document,
        pipeline._activity_names['validate_version']: pipeline._activity_validate_version,
        pipeline._activity_names['activate_version']: pipeline._activity_activate_version,
        pipeline._activity_names[
            'publish_activation_event'
        ]: pipeline._activity_publish_activation_event,
        pipeline._activity_names[
            'register_foundry_iq_knowledge_source'
        ]: pipeline._activity_register_foundry_iq_knowledge_source,
        pipeline._activity_names['update_status']: pipeline._activity_update_status,
    }


def _drive_one_generation(dispatch, gen, activity_ctx):
    """Drives a single orchestrator generation to `StopIteration`, executing each
    yielded call against `dispatch`. Returns the generation's return value --
    which, for `_orchestrate_ingestion`, is `None` when it ended via
    `continue_as_new` rather than by actually finishing.
    """
    sent = None
    while True:
        try:
            pending = gen.send(sent)
        except StopIteration as stop:
            return stop.value
        sent = dispatch[pending.activity_name](activity_ctx, pending.input)


def _drive_with_real_activities(pipeline, orchestrator_fn, ctx, wf_input, activity_ctx):
    """Drives an orchestrator to completion, executing each yielded call
    against the pipeline's real `_activity_*` methods -- exercising real
    state reads/writes and idempotency checks without a live durabletask
    engine. Transparently follows `continue_as_new` the way a real
    durabletask worker would (ending one generation and starting the next
    with its recorded input), accumulating every generation's calls onto the
    same `ctx.calls` so a caller sees the full cross-generation history.
    """
    dispatch = _activity_dispatch(pipeline)
    current_input = wf_input
    while True:
        ctx.continue_as_new_input = None
        final = _drive_one_generation(dispatch, orchestrator_fn(ctx, current_input), activity_ctx)
        if ctx.continue_as_new_input is None:
            return final
        current_input = ctx.continue_as_new_input


def _recording_dispatch(pipeline, results_sink):
    """Like `_activity_dispatch`, but appends each activity's result to `results_sink`
    in call order -- for capturing a real run's results to replay later."""
    wrapped = {}
    for name, fn in _activity_dispatch(pipeline).items():

        def make_wrapper(fn=fn):
            def wrapper(activity_ctx, input):
                result = fn(activity_ctx, input)
                results_sink.append(result)
                return result

            return wrapper

        wrapped[name] = make_wrapper()
    return wrapped


def _drive_with_canned_results(gen, canned_results):
    """Drives a generator using pre-recorded results rather than executing
    activities -- a true replay: durabletask never re-invokes an activity
    whose result is already in history, it just feeds the cached result back.
    """
    sent = None
    results = iter(canned_results)
    while True:
        try:
            gen.send(sent)
        except StopIteration as stop:
            return stop.value
        sent = next(results)


def _pipeline(config=None, **overrides):
    kwargs = dict(
        source=_FakeSource(),
        parser=_FakeParser(),
        splitter=_FakeSplitter(),
        embedder=_FakeEmbedder(),
        vector_store=_FakeVectorStore(),
        state_store_name='rag-pipeline-state',
        pipeline_id='company-knowledge',
        config=config or PipelineConfig(),
        workflow_runtime=mock.Mock(),
        workflow_client=mock.Mock(),
        dapr_client=_FakeDaprClient(),
    )
    kwargs.update(overrides)
    return DurableRAGPipeline(**kwargs)


def _work_item(document_id, name=None, etag=None):
    return DocumentWorkItem(
        document_id=document_id,
        provider='s3',
        uri=document_id,
        name=name or document_id,
        source_etag=etag,
    )


def _activity_ctx(workflow_id='wf-instance-1'):
    return SimpleNamespace(workflow_id=workflow_id)


class DurableRAGPipelineConstructionTest(unittest.TestCase):
    def test_pipeline_id_defaults_to_the_vector_store_index_name(self):
        pipeline = _pipeline(
            pipeline_id=None, vector_store=_FakeVectorStore(index_name='from-store')
        )
        self.assertEqual(pipeline._pipeline_id, 'from-store')

    def test_registers_two_workflows_and_eight_activities(self):
        runtime = mock.Mock()
        _pipeline(workflow_runtime=runtime)
        self.assertEqual(runtime.register_workflow.call_count, 2)
        self.assertEqual(runtime.register_activity.call_count, 8)

    def test_activity_names_are_namespaced_by_pipeline_id(self):
        pipeline = _pipeline(pipeline_id='my-pipeline')
        for name in pipeline._activity_names.values():
            self.assertIn('my-pipeline', name)

    def test_foundry_iq_knowledge_source_requires_a_vector_store_that_supports_it(self):
        with self.assertRaises(ValueError):
            _pipeline(
                vector_store=_FakeSimpleVectorStore(),
                foundry_iq_knowledge_source=FoundryIQKnowledgeSourceConfig(name='ks'),
            )

    def test_foundry_iq_knowledge_source_is_accepted_when_the_vector_store_supports_it(self):
        # _FakeVectorStore implements register_foundry_iq_knowledge_source -- must not raise.
        _pipeline(
            vector_store=_FakeVectorStore(),
            foundry_iq_knowledge_source=FoundryIQKnowledgeSourceConfig(name='ks'),
        )


class DurableRAGPipelineStartTest(unittest.TestCase):
    def test_schedules_a_new_workflow_with_a_stable_instance_id(self):
        workflow_client = mock.Mock()
        workflow_client.get_workflow_state.return_value = None
        workflow_client.schedule_new_workflow.return_value = 'rag-ingest-company-knowledge-2026-09'
        pipeline = _pipeline(workflow_client=workflow_client)

        instance_id = pipeline.start(version='2026-09')

        self.assertEqual(instance_id, 'rag-ingest-company-knowledge-2026-09')
        workflow_client.schedule_new_workflow.assert_called_once()
        _, kwargs = workflow_client.schedule_new_workflow.call_args
        self.assertEqual(kwargs['instance_id'], 'rag-ingest-company-knowledge-2026-09')

    def test_does_not_reschedule_a_run_that_is_still_in_flight(self):
        from dapr.ext.workflow import WorkflowStatus

        workflow_client = mock.Mock()
        workflow_client.get_workflow_state.return_value = SimpleNamespace(
            runtime_status=WorkflowStatus.RUNNING
        )
        pipeline = _pipeline(workflow_client=workflow_client)

        instance_id = pipeline.start(version='2026-09')

        self.assertEqual(instance_id, 'rag-ingest-company-knowledge-2026-09')
        workflow_client.schedule_new_workflow.assert_not_called()

    def test_reschedules_after_a_prior_terminal_run(self):
        from dapr.ext.workflow import WorkflowStatus

        workflow_client = mock.Mock()
        workflow_client.get_workflow_state.return_value = SimpleNamespace(
            runtime_status=WorkflowStatus.FAILED
        )
        pipeline = _pipeline(workflow_client=workflow_client)

        pipeline.start(version='2026-09')

        workflow_client.schedule_new_workflow.assert_called_once()


class DurableRAGPipelineActivateVersionTest(unittest.TestCase):
    def test_schedules_the_standalone_activation_workflow(self):
        workflow_client = mock.Mock()
        workflow_client.get_workflow_state.return_value = None
        workflow_client.schedule_new_workflow.return_value = (
            'rag-activate-company-knowledge-2026-09'
        )
        pipeline = _pipeline(workflow_client=workflow_client)

        instance_id = pipeline.activate_version('2026-09')

        self.assertEqual(instance_id, 'rag-activate-company-knowledge-2026-09')
        _, kwargs = workflow_client.schedule_new_workflow.call_args
        self.assertEqual(
            kwargs['input'], {'pipeline_id': 'company-knowledge', 'version': '2026-09'}
        )


class DurableRAGPipelineStatusTest(unittest.TestCase):
    def test_get_status_reflects_what_the_update_status_activity_wrote(self):
        pipeline = _pipeline()
        pipeline._activity_update_status(
            _activity_ctx(),
            {
                'pipeline_id': 'company-knowledge',
                'version': '2026-09',
                'stage': 'processing_documents',
            },
        )
        status = pipeline.get_status('2026-09')
        self.assertEqual(status.stage, 'processing_documents')

    def test_resolve_active_version_reflects_activation(self):
        pipeline = _pipeline()
        self.assertIsNone(pipeline.resolve_active_version())
        pipeline._activity_activate_version(
            _activity_ctx(),
            {'pipeline_id': 'company-knowledge', 'version': '2026-09', 'manifest_hash': 'h1'},
        )
        self.assertEqual(pipeline.resolve_active_version(), '2026-09')

    def test_a_new_instance_re_running_a_version_resets_counters_instead_of_accumulating(self):
        """Regression test: a real integration run (see test_pipeline_integration.py) caught
        this -- re-running a version's stable instance ID under a *different* explicit
        instance_id (start()'s instance_id= override, not just resume-with-the-same-ID) left
        `workflow_instance_id` stuck on whichever instance first wrote status, and kept
        incrementing counters on top of the prior run's instead of starting over."""
        pipeline = _pipeline()
        pipeline._activity_update_status(
            _activity_ctx(workflow_id='wf-instance-1'),
            {
                'pipeline_id': 'company-knowledge',
                'version': '2026-09',
                'stage': 'completed',
                'outcomes': [
                    {
                        'document_id': 'doc-1',
                        'status': DocumentOutcomeStatus.COMPLETED.value,
                        'chunk_count': 2,
                        'embedded_chunk_count': 2,
                    },
                ],
            },
        )
        first = pipeline.get_status('2026-09')
        self.assertEqual(first.workflow_instance_id, 'wf-instance-1')
        self.assertEqual(first.completed_documents, 1)

        pipeline._activity_update_status(
            _activity_ctx(workflow_id='wf-instance-2'),
            {
                'pipeline_id': 'company-knowledge',
                'version': '2026-09',
                'stage': 'completed',
                'outcomes': [
                    {
                        'document_id': 'doc-1',
                        'status': DocumentOutcomeStatus.SKIPPED.value,
                        'reused_chunk_count': 2,
                    },
                ],
            },
        )
        second = pipeline.get_status('2026-09')
        self.assertEqual(second.workflow_instance_id, 'wf-instance-2')
        self.assertEqual(second.completed_documents, 0)
        self.assertEqual(second.skipped_documents, 1)
        self.assertEqual(second.reused_chunks, 2)


class ActivityDiscoverAndManifestTest(unittest.TestCase):
    def test_writes_a_manifest_and_returns_its_summary(self):
        documents = [
            SourceDocument(
                document_id=f's3://b/{i}.txt',
                provider=SourceProvider.S3,
                uri=f's3://b/{i}.txt',
                name=f'{i}.txt',
            )
            for i in range(3)
        ]
        pipeline = _pipeline(source=_FakeSource(documents=documents))

        summary_raw = pipeline._activity_discover_and_manifest(
            _activity_ctx(),
            {
                'pipeline_id': 'company-knowledge',
                'version': '2026-09',
                'page_size': 2,
                'prefix': None,
            },
        )

        self.assertEqual(summary_raw['total_documents'], 3)
        page0 = pipeline._activity_get_manifest_batch(
            _activity_ctx(),
            {'pipeline_id': 'company-knowledge', 'version': '2026-09', 'page_index': 0},
        )
        self.assertEqual(len(page0['items']), 2)


class ActivityProcessDocumentTest(unittest.TestCase):
    def _base_raw(self, work_item, pipeline_fingerprint='fp-1', document_ordinal=0):
        return {
            'work_item': dataclasses.asdict(work_item),
            'pipeline_id': 'company-knowledge',
            'version': '2026-09',
            'pipeline_fingerprint': pipeline_fingerprint,
            'document_ordinal': document_ordinal,
        }

    def test_completes_a_fresh_document(self):
        work_item = _work_item('doc-1')
        source = _FakeSource(content_by_id={'doc-1': b'sentence one|sentence two'})
        vector_store = _FakeVectorStore()
        pipeline = _pipeline(source=source, vector_store=vector_store)

        raw = self._base_raw(work_item, pipeline_fingerprint=pipeline._pipeline_fingerprint)
        outcome_raw = pipeline._activity_process_document(_activity_ctx(), raw)

        self.assertEqual(outcome_raw['status'], DocumentOutcomeStatus.COMPLETED.value)
        self.assertEqual(outcome_raw['chunk_count'], 2)
        self.assertEqual(outcome_raw['embedded_chunk_count'], 2)
        self.assertEqual(len(vector_store.upserted), 2)

    def test_skips_an_already_completed_document_without_touching_the_embedder(self):
        work_item = _work_item('doc-1')
        source = _FakeSource(content_by_id={'doc-1': b'sentence one'})
        embedder = _FakeEmbedder()
        pipeline = _pipeline(source=source, embedder=embedder)
        raw = self._base_raw(work_item, pipeline_fingerprint=pipeline._pipeline_fingerprint)

        first = pipeline._activity_process_document(_activity_ctx(), raw)
        self.assertEqual(first['status'], DocumentOutcomeStatus.COMPLETED.value)
        self.assertEqual(len(embedder.calls), 1)

        second = pipeline._activity_process_document(_activity_ctx(), raw)
        self.assertEqual(second['status'], DocumentOutcomeStatus.SKIPPED.value)
        self.assertEqual(second['reused_chunk_count'], first['chunk_count'])
        self.assertEqual(len(embedder.calls), 1)  # no new embedding calls

    def test_resumes_after_a_simulated_crash_without_re_embedding_the_completed_batch(self):
        work_item = _work_item('doc-1')
        # Two chunks -> two embedding batches at batch size 1; the embedder fails
        # only on the *second* batch's text, simulating a crash partway through.
        source = _FakeSource(content_by_id={'doc-1': b'first sentence|second sentence'})
        embedder = _FakeEmbedder(fail_on_texts={'second sentence'})
        vector_store = _FakeVectorStore()
        pipeline = _pipeline(
            source=source,
            embedder=embedder,
            vector_store=vector_store,
            config=PipelineConfig(embedding_batch_size=1),
        )
        raw = self._base_raw(work_item, pipeline_fingerprint=pipeline._pipeline_fingerprint)

        with self.assertRaises(TransientEmbeddingError):
            pipeline._activity_process_document(_activity_ctx(), raw)

        # The first batch's vector is already durably upserted even though the
        # activity as a whole "failed" (simulating the crash). _FakeEmbedder records
        # a call before checking whether it should fail, so the failed attempt at
        # the second batch shows up here too -- only the *vector_store* side proves
        # which batch actually completed.
        self.assertEqual(len(vector_store.upserted), 1)
        self.assertEqual(embedder.calls, [['first sentence'], ['second sentence']])

        embedder._fail_on_texts.clear()  # the retry no longer hits the failure
        outcome_raw = pipeline._activity_process_document(_activity_ctx(), raw)

        self.assertEqual(outcome_raw['status'], DocumentOutcomeStatus.COMPLETED.value)
        self.assertEqual(len(vector_store.upserted), 2)
        # The retry only embeds the second batch again -- a third call, not a
        # second attempt at the first batch, which its recorded progress skips.
        self.assertEqual(
            embedder.calls, [['first sentence'], ['second sentence'], ['second sentence']]
        )

    def test_a_document_changed_since_discovery_raises_a_retryable_error(self):
        work_item = _work_item('doc-1', etag='etag-at-discovery')
        source = _FakeSource(
            content_by_id={'doc-1': b'hello'},
            metadata_sequence_by_id={'doc-1': [SourceMetadata(etag='etag-changed')]},
        )
        pipeline = _pipeline(source=source)
        raw = self._base_raw(work_item, pipeline_fingerprint=pipeline._pipeline_fingerprint)

        from dapr.ext.rag.errors import DocumentChangedError

        with self.assertRaises(DocumentChangedError):
            pipeline._activity_process_document(_activity_ctx(), raw)

    def test_a_non_retryable_parser_failure_becomes_a_failed_outcome_not_an_exception(self):
        work_item = _work_item('doc-1')
        source = _FakeSource(content_by_id={'doc-1': b'hello'})
        parser = _FakeParser(fail_for_document_ids={'doc-1'})
        pipeline = _pipeline(source=source, parser=parser)
        raw = self._base_raw(work_item, pipeline_fingerprint=pipeline._pipeline_fingerprint)

        outcome_raw = pipeline._activity_process_document(_activity_ctx(), raw)

        self.assertEqual(outcome_raw['status'], DocumentOutcomeStatus.FAILED.value)
        self.assertFalse(outcome_raw['retryable'])
        self.assertEqual(outcome_raw['error_type'], 'DocumentParseError')

    def test_attempts_counter_increments_across_calls(self):
        work_item = _work_item('doc-1')
        source = _FakeSource(content_by_id={'doc-1': b'hello'})
        parser = _FakeParser(
            fail_for_document_ids={'doc-1'}
        )  # always "fails" (non-retryable), no state churn
        pipeline = _pipeline(source=source, parser=parser)
        raw = self._base_raw(work_item, pipeline_fingerprint=pipeline._pipeline_fingerprint)

        first = pipeline._activity_process_document(_activity_ctx(), raw)
        second = pipeline._activity_process_document(_activity_ctx(), raw)
        self.assertEqual(first['attempts'], 1)
        self.assertEqual(second['attempts'], 2)

    def test_provenance_never_includes_secret_values(self):
        work_item = _work_item('doc-1')
        source = _FakeSource(content_by_id={'doc-1': b'hello there'})
        vector_store = _FakeVectorStore()
        pipeline = _pipeline(source=source, vector_store=vector_store)
        raw = self._base_raw(work_item, pipeline_fingerprint=pipeline._pipeline_fingerprint)

        pipeline._activity_process_document(_activity_ctx(), raw)

        for _version, record in vector_store.upserted:
            serialized = str(record.metadata)
            self.assertNotIn(_SECRET_API_KEY, serialized)
            self.assertNotIn(_SECRET_CONNECTION_STRING, serialized)


class ActivityValidateVersionTest(unittest.TestCase):
    def test_invalid_when_no_documents_were_expected(self):
        pipeline = _pipeline()
        pipeline._activity_discover_and_manifest(
            _activity_ctx(),
            {
                'pipeline_id': 'company-knowledge',
                'version': '2026-09',
                'page_size': 10,
                'prefix': None,
            },
        )
        result_raw = pipeline._activity_validate_version(
            _activity_ctx(), {'pipeline_id': 'company-knowledge', 'version': '2026-09'}
        )
        self.assertFalse(result_raw['valid'])

    def test_valid_once_every_document_completed(self):
        documents = [
            SourceDocument(
                document_id='s3://b/a.txt',
                provider=SourceProvider.S3,
                uri='s3://b/a.txt',
                name='a.txt',
            )
        ]
        source = _FakeSource(documents=documents, content_by_id={'s3://b/a.txt': b'hello'})
        pipeline = _pipeline(source=source)
        pipeline._activity_discover_and_manifest(
            _activity_ctx(),
            {
                'pipeline_id': 'company-knowledge',
                'version': '2026-09',
                'page_size': 10,
                'prefix': None,
            },
        )
        batch = pipeline._activity_get_manifest_batch(
            _activity_ctx(),
            {'pipeline_id': 'company-knowledge', 'version': '2026-09', 'page_index': 0},
        )
        [item] = batch['items']
        pipeline._activity_process_document(
            _activity_ctx(),
            {
                'work_item': item,
                'pipeline_id': 'company-knowledge',
                'version': '2026-09',
                'pipeline_fingerprint': pipeline._pipeline_fingerprint,
                'document_ordinal': 0,
            },
        )

        result_raw = pipeline._activity_validate_version(
            _activity_ctx(), {'pipeline_id': 'company-knowledge', 'version': '2026-09'}
        )
        self.assertTrue(result_raw['valid'])


class ActivityActivateVersionTest(unittest.TestCase):
    def test_activates_when_nothing_was_active_before(self):
        pipeline = _pipeline()
        record_raw = pipeline._activity_activate_version(
            _activity_ctx(),
            {'pipeline_id': 'company-knowledge', 'version': '2026-09', 'manifest_hash': 'h1'},
        )
        self.assertEqual(record_raw['active_version'], '2026-09')
        self.assertIsNone(record_raw['previous_version'])

    def test_records_the_previous_version_on_a_later_activation(self):
        pipeline = _pipeline()
        pipeline._activity_activate_version(
            _activity_ctx(),
            {'pipeline_id': 'company-knowledge', 'version': '2026-08', 'manifest_hash': 'h1'},
        )
        record_raw = pipeline._activity_activate_version(
            _activity_ctx(),
            {'pipeline_id': 'company-knowledge', 'version': '2026-09', 'manifest_hash': 'h2'},
        )
        self.assertEqual(record_raw['active_version'], '2026-09')
        self.assertEqual(record_raw['previous_version'], '2026-08')

    def test_repeated_activation_of_the_same_version_is_a_no_op(self):
        pipeline = _pipeline()
        raw = {'pipeline_id': 'company-knowledge', 'version': '2026-09', 'manifest_hash': 'h1'}
        first = pipeline._activity_activate_version(_activity_ctx(), raw)
        state_size_after_first = len(pipeline._dapr_client._store)
        second = pipeline._activity_activate_version(_activity_ctx(), raw)
        self.assertEqual(first, second)
        self.assertEqual(
            len(pipeline._dapr_client._store), state_size_after_first
        )  # no extra write

    def test_calls_the_store_native_activation_hook_before_the_dapr_state_write(self):
        vector_store = _FakeVectorStore()
        pipeline = _pipeline(vector_store=vector_store)
        pipeline._activity_activate_version(
            _activity_ctx(),
            {'pipeline_id': 'company-knowledge', 'version': '2026-09', 'manifest_hash': 'h1'},
        )
        self.assertEqual(vector_store.activate_version_calls, [('2026-09', None)])

    def test_repeated_activation_does_not_call_the_store_native_hook_again(self):
        vector_store = _FakeVectorStore()
        pipeline = _pipeline(vector_store=vector_store)
        raw = {'pipeline_id': 'company-knowledge', 'version': '2026-09', 'manifest_hash': 'h1'}
        pipeline._activity_activate_version(_activity_ctx(), raw)
        pipeline._activity_activate_version(_activity_ctx(), raw)
        self.assertEqual(len(vector_store.activate_version_calls), 1)

    def test_a_later_activation_passes_the_previous_version_to_the_store(self):
        vector_store = _FakeVectorStore()
        pipeline = _pipeline(vector_store=vector_store)
        pipeline._activity_activate_version(
            _activity_ctx(),
            {'pipeline_id': 'company-knowledge', 'version': '2026-08', 'manifest_hash': 'h1'},
        )
        pipeline._activity_activate_version(
            _activity_ctx(),
            {'pipeline_id': 'company-knowledge', 'version': '2026-09', 'manifest_hash': 'h2'},
        )
        self.assertEqual(vector_store.activate_version_calls[-1], ('2026-09', '2026-08'))


class ActivityPublishActivationEventTest(unittest.TestCase):
    def test_no_op_when_pubsub_is_not_configured(self):
        pipeline = _pipeline()
        result = pipeline._activity_publish_activation_event(
            _activity_ctx(), {'activation_record': {}}
        )
        self.assertFalse(result['published'])

    def test_publishes_when_pubsub_is_configured(self):
        dapr_client = _FakeDaprClient()
        pipeline = _pipeline(dapr_client=dapr_client, pubsub_name='pubsub')
        result = pipeline._activity_publish_activation_event(
            _activity_ctx(), {'activation_record': {'active_version': '2026-09'}}
        )
        self.assertTrue(result['published'])
        self.assertEqual(len(dapr_client.published_events), 1)

    def test_a_publish_failure_is_swallowed(self):
        dapr_client = mock.Mock()
        dapr_client.publish_event.side_effect = RuntimeError('pubsub down')
        pipeline = _pipeline(dapr_client=dapr_client, pubsub_name='pubsub')
        result = pipeline._activity_publish_activation_event(
            _activity_ctx(), {'activation_record': {}}
        )
        self.assertFalse(result['published'])


class ActivityRegisterFoundryIQKnowledgeSourceTest(unittest.TestCase):
    def test_no_op_when_not_configured(self):
        vector_store = _FakeVectorStore()
        pipeline = _pipeline(vector_store=vector_store)
        result = pipeline._activity_register_foundry_iq_knowledge_source(
            _activity_ctx(), {'pipeline_id': 'company-knowledge', 'version': '2026-09'}
        )
        self.assertFalse(result['registered'])
        self.assertEqual(vector_store.foundry_iq_registration_calls, [])

    def test_registers_against_the_vector_store_when_configured(self):
        vector_store = _FakeVectorStore()
        pipeline = _pipeline(
            vector_store=vector_store,
            foundry_iq_knowledge_source=FoundryIQKnowledgeSourceConfig(
                name='company-knowledge-ks',
                description='desc',
                source_data_fields=('title',),
                search_fields=('content',),
            ),
        )
        result = pipeline._activity_register_foundry_iq_knowledge_source(
            _activity_ctx(), {'pipeline_id': 'company-knowledge', 'version': '2026-09'}
        )
        self.assertTrue(result['registered'])
        self.assertEqual(
            vector_store.foundry_iq_registration_calls,
            [
                {
                    'version': '2026-09',
                    'name': 'company-knowledge-ks',
                    'description': 'desc',
                    'source_data_fields': ['title'],
                    'search_fields': ['content'],
                }
            ],
        )

    def test_a_registration_failure_is_swallowed(self):
        vector_store = _FakeVectorStore()
        vector_store.foundry_iq_registration_error = RuntimeError('search down')
        pipeline = _pipeline(
            vector_store=vector_store,
            foundry_iq_knowledge_source=FoundryIQKnowledgeSourceConfig(name='ks'),
        )
        result = pipeline._activity_register_foundry_iq_knowledge_source(
            _activity_ctx(), {'pipeline_id': 'company-knowledge', 'version': '2026-09'}
        )
        self.assertFalse(result['registered'])


class OrchestratorIngestionEndToEndTest(unittest.TestCase):
    def _documents(self, n):
        return [
            SourceDocument(
                document_id=f's3://b/{i}.txt',
                provider=SourceProvider.S3,
                uri=f's3://b/{i}.txt',
                name=f'{i}.txt',
            )
            for i in range(n)
        ]

    def test_completes_validates_and_activates_a_small_run(self):
        documents = self._documents(2)
        content_by_id = {d.document_id: f'chunk-{d.document_id}'.encode() for d in documents}
        vector_store = _FakeVectorStore()
        pipeline = _pipeline(
            source=_FakeSource(documents=documents, content_by_id=content_by_id),
            vector_store=vector_store,
        )
        wf_input = to_wire(
            _IngestionState(
                pipeline_id='company-knowledge',
                version='2026-09',
                activate_when_complete=True,
                fail_fast=False,
                page_size=10,
                embedding_batch_size=64,
                max_activity_attempts=5,
                first_retry_interval_seconds=1.0,
                backoff_coefficient=2.0,
                max_retry_interval_seconds=30.0,
            )
        )

        ctx = _FakeWorkflowContext()
        final = _drive_with_real_activities(
            pipeline, pipeline._orchestrate_ingestion, ctx, wf_input, _activity_ctx()
        )

        self.assertEqual(final['stage'], PipelineStage.COMPLETED.value)
        self.assertTrue(final['validation_succeeded'])
        self.assertTrue(final['activation_succeeded'])
        self.assertEqual(final['active_version'], '2026-09')
        self.assertEqual(pipeline.resolve_active_version(), '2026-09')
        self.assertEqual(len(vector_store.upserted), 2)

    def test_registers_the_foundry_iq_knowledge_source_after_activation_when_configured(self):
        documents = self._documents(1)
        content_by_id = {d.document_id: b'chunk one' for d in documents}
        vector_store = _FakeVectorStore()
        pipeline = _pipeline(
            source=_FakeSource(documents=documents, content_by_id=content_by_id),
            vector_store=vector_store,
            foundry_iq_knowledge_source=FoundryIQKnowledgeSourceConfig(name='company-knowledge-ks'),
        )
        wf_input = to_wire(
            _IngestionState(
                pipeline_id='company-knowledge',
                version='2026-09',
                activate_when_complete=True,
                fail_fast=False,
                page_size=10,
                embedding_batch_size=64,
                max_activity_attempts=5,
                first_retry_interval_seconds=1.0,
                backoff_coefficient=2.0,
                max_retry_interval_seconds=30.0,
            )
        )

        final = _drive_with_real_activities(
            pipeline,
            pipeline._orchestrate_ingestion,
            _FakeWorkflowContext(),
            wf_input,
            _activity_ctx(),
        )

        self.assertTrue(final['activation_succeeded'])
        self.assertEqual(
            vector_store.foundry_iq_registration_calls,
            [
                {
                    'version': '2026-09',
                    'name': 'company-knowledge-ks',
                    'description': None,
                    'source_data_fields': [],
                    'search_fields': [],
                }
            ],
        )

    def test_does_not_register_a_foundry_iq_knowledge_source_when_not_configured(self):
        documents = self._documents(1)
        content_by_id = {d.document_id: b'chunk one' for d in documents}
        vector_store = _FakeVectorStore()
        pipeline = _pipeline(
            source=_FakeSource(documents=documents, content_by_id=content_by_id),
            vector_store=vector_store,
        )
        wf_input = to_wire(
            _IngestionState(
                pipeline_id='company-knowledge',
                version='2026-09',
                activate_when_complete=True,
                fail_fast=False,
                page_size=10,
                embedding_batch_size=64,
                max_activity_attempts=5,
                first_retry_interval_seconds=1.0,
                backoff_coefficient=2.0,
                max_retry_interval_seconds=30.0,
            )
        )

        _drive_with_real_activities(
            pipeline,
            pipeline._orchestrate_ingestion,
            _FakeWorkflowContext(),
            wf_input,
            _activity_ctx(),
        )

        self.assertEqual(vector_store.foundry_iq_registration_calls, [])

    def test_fail_fast_false_keeps_processing_after_one_document_fails(self):
        documents = self._documents(2)
        content_by_id = {
            documents[0].document_id: b'ok content',
            documents[1].document_id: b'bad content',
        }
        parser = _FakeParser(fail_for_document_ids={documents[1].document_id})
        pipeline = _pipeline(
            source=_FakeSource(documents=documents, content_by_id=content_by_id),
            parser=parser,
            config=PipelineConfig(fail_fast=False),
        )
        wf_input = to_wire(
            _IngestionState(
                pipeline_id='company-knowledge',
                version='2026-09',
                activate_when_complete=True,
                fail_fast=False,
                page_size=10,
                embedding_batch_size=64,
                max_activity_attempts=5,
                first_retry_interval_seconds=1.0,
                backoff_coefficient=2.0,
                max_retry_interval_seconds=30.0,
            )
        )

        final = _drive_with_real_activities(
            pipeline,
            pipeline._orchestrate_ingestion,
            _FakeWorkflowContext(),
            wf_input,
            _activity_ctx(),
        )

        # One document failed, so validation (and therefore activation) must not succeed --
        # a partially-built version is never exposed as active.
        self.assertFalse(final['validation_succeeded'])
        self.assertFalse(final['activation_succeeded'])
        self.assertIsNone(pipeline.resolve_active_version())
        self.assertEqual(final['failed_documents'], 1)
        self.assertEqual(final['completed_documents'], 1)

    def test_continues_as_new_between_bounded_batches(self):
        documents = self._documents(2)
        content_by_id = {d.document_id: b'hello' for d in documents}
        pipeline = _pipeline(
            source=_FakeSource(documents=documents, content_by_id=content_by_id),
            config=PipelineConfig(max_concurrent_documents=1),  # forces 2 batches for 2 documents
        )
        wf_input = to_wire(
            _IngestionState(
                pipeline_id='company-knowledge',
                version='2026-09',
                activate_when_complete=False,
                fail_fast=False,
                page_size=1,
                embedding_batch_size=64,
                max_activity_attempts=5,
                first_retry_interval_seconds=1.0,
                backoff_coefficient=2.0,
                max_retry_interval_seconds=30.0,
            )
        )

        ctx = _FakeWorkflowContext()
        dispatch = _activity_dispatch(pipeline)
        final = _drive_one_generation(
            dispatch, pipeline._orchestrate_ingestion(ctx, wf_input), _activity_ctx()
        )

        # This first generation processes exactly one bounded batch (one document,
        # since max_concurrent_documents=1) and then ends via continue_as_new --
        # it never reaches validation/activation itself.
        self.assertIsNone(final)
        self.assertIsNotNone(ctx.continue_as_new_input)
        self.assertEqual(ctx.continue_as_new_input['cursor'], 1)
        self.assertTrue(ctx.continue_as_new_input['manifest_ready'])

    def test_replay_produces_the_identical_activity_call_sequence(self):
        """Feeding a fresh generation the exact results a real run produced for it
        must yield the exact same (name, input) call sequence -- the replay-safety
        guarantee durabletask's history caching depends on: on replay it never
        re-invokes an activity, it just feeds the *same* generation the recorded
        result for each call in order.

        Deliberately exercises one generation in isolation (not the multi-
        generation continue_as_new chain `_drive_with_real_activities` follows):
        durabletask history, and therefore replay, belongs to one generation --
        continue_as_new starts a *new* one with fresh history, which is a
        different (and separately covered, by
        test_continues_as_new_between_bounded_batches) guarantee than replay.
        """
        documents = self._documents(2)
        content_by_id = {d.document_id: b'hello' for d in documents}
        pipeline = _pipeline(source=_FakeSource(documents=documents, content_by_id=content_by_id))
        wf_input = to_wire(
            _IngestionState(
                pipeline_id='company-knowledge',
                version='2026-09',
                activate_when_complete=True,
                fail_fast=False,
                page_size=10,
                embedding_batch_size=64,
                max_activity_attempts=5,
                first_retry_interval_seconds=1.0,
                backoff_coefficient=2.0,
                max_retry_interval_seconds=30.0,
            )
        )

        # Run for real once, recording this generation's actual results in call order.
        real_results: list = []
        first_ctx = _FakeWorkflowContext()
        _drive_one_generation(
            _recording_dispatch(pipeline, real_results),
            pipeline._orchestrate_ingestion(first_ctx, wf_input),
            _activity_ctx(),
        )
        first_calls = [(c.activity_name, c.input) for c in first_ctx.calls]

        # True replay: a brand new generation, fed only the recorded results above --
        # no activity is actually re-invoked.
        second_ctx = _FakeWorkflowContext()
        _drive_with_canned_results(
            pipeline._orchestrate_ingestion(second_ctx, wf_input), real_results
        )
        second_calls = [(c.activity_name, c.input) for c in second_ctx.calls]

        self.assertEqual(first_calls, second_calls)


class OrchestratorActivationTest(unittest.TestCase):
    def test_raises_when_validation_fails(self):
        pipeline = _pipeline()  # nothing discovered/processed -> validation will fail
        wf_input = to_wire(_ActivationState(pipeline_id='company-knowledge', version='2026-09'))

        from dapr.ext.rag.errors import VersionValidationError

        with self.assertRaises(VersionValidationError):
            _drive_with_real_activities(
                pipeline,
                pipeline._orchestrate_activation,
                _FakeWorkflowContext(),
                wf_input,
                _activity_ctx(),
            )

    def test_activates_a_previously_built_version(self):
        documents = [
            SourceDocument(
                document_id='s3://b/a.txt',
                provider=SourceProvider.S3,
                uri='s3://b/a.txt',
                name='a.txt',
            )
        ]
        pipeline = _pipeline(
            source=_FakeSource(documents=documents, content_by_id={'s3://b/a.txt': b'hello'})
        )
        # Build the version first, without activating.
        ingest_input = to_wire(
            _IngestionState(
                pipeline_id='company-knowledge',
                version='2026-09',
                activate_when_complete=False,
                fail_fast=False,
                page_size=10,
                embedding_batch_size=64,
                max_activity_attempts=5,
                first_retry_interval_seconds=1.0,
                backoff_coefficient=2.0,
                max_retry_interval_seconds=30.0,
            )
        )
        _drive_with_real_activities(
            pipeline,
            pipeline._orchestrate_ingestion,
            _FakeWorkflowContext(),
            ingest_input,
            _activity_ctx(),
        )
        self.assertIsNone(pipeline.resolve_active_version())

        activate_input = to_wire(
            _ActivationState(pipeline_id='company-knowledge', version='2026-09')
        )
        _drive_with_real_activities(
            pipeline,
            pipeline._orchestrate_activation,
            _FakeWorkflowContext(),
            activate_input,
            _activity_ctx(),
        )

        self.assertEqual(pipeline.resolve_active_version(), '2026-09')


if __name__ == '__main__':
    unittest.main()
