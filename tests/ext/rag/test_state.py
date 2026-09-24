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

import json
import unittest
from unittest import mock

import grpc

from dapr.ext.rag.errors import ActivationConflictError
from dapr.ext.rag.models import (
    ActivationRecord,
    CompletionRecord,
    DocumentWorkItem,
    EmbedProgressRecord,
    PipelineStatus,
)
from dapr.ext.rag.state import PipelineStateStore


def _state_response(value, etag=None):
    response = mock.Mock()
    response.data = None if value is None else json.dumps(value).encode('utf-8')
    response.etag = etag
    return response


class _FakeRpcError(grpc.RpcError):
    """A real `grpc.RpcError` instance (Mock can't be `raise`d as one)."""

    def __init__(self, status_code):
        super().__init__()
        self._status_code = status_code

    def code(self):
        return self._status_code

    def details(self):
        return 'boom'


def _grpc_error(status_code):
    return _FakeRpcError(status_code)


def _work_items(n):
    return [
        DocumentWorkItem(
            document_id=f'doc-{i}', provider='s3', uri=f's3://b/doc-{i}', name=f'doc-{i}'
        )
        for i in range(n)
    ]


@mock.patch('dapr.ext.rag.state.DaprClient')
class PipelineStateStoreTest(unittest.TestCase):
    def setUp(self):
        self.mock_client = mock.Mock()
        self.mock_client.get_state.return_value = _state_response(None)
        self.store = PipelineStateStore(state_store_name='statestore', dapr_client=self.mock_client)

    # -- manifest ---------------------------------------------------------

    def test_write_manifest_pages_documents_and_writes_a_meta_key(self, _):
        documents = _work_items(5)
        summary = self.store.write_manifest(
            pipeline_id='p1',
            version='v1',
            documents=documents,
            page_size=2,
            manifest_hash='hash-1',
            created_at='2026-09-10T00:00:00+00:00',
        )
        self.assertEqual(summary.total_documents, 5)
        self.assertEqual(summary.manifest_hash, 'hash-1')
        # 3 pages (2, 2, 1) + 1 meta key
        self.assertEqual(self.mock_client.save_state.call_count, 4)

    def test_read_manifest_page_reconstructs_document_work_items(self, _):
        documents = _work_items(2)
        page_json = [
            {
                'document_id': d.document_id,
                'provider': d.provider,
                'uri': d.uri,
                'name': d.name,
                'source_etag': None,
                'source_version_id': None,
                'source_content_length': None,
            }
            for d in documents
        ]
        self.mock_client.get_state.return_value = _state_response(page_json)
        result = self.store.read_manifest_page(pipeline_id='p1', version='v1', page_index=0)
        self.assertEqual(result, documents)

    def test_read_manifest_meta_returns_none_when_absent(self, _):
        self.assertIsNone(self.store.read_manifest_meta(pipeline_id='p1', version='v1'))

    # -- completion ---------------------------------------------------------

    def test_write_then_read_completion_round_trips(self, _):
        record = CompletionRecord(
            document_id='doc-1',
            source_content_hash='h1',
            pipeline_fingerprint='fp1',
            chunk_count=3,
            embedded_chunk_count=3,
            completed_at='2026-09-10T00:00:00+00:00',
        )
        self.store.write_completion(pipeline_id='p1', version='v1', record=record)
        saved_value = self.mock_client.save_state.call_args.kwargs['value']
        self.mock_client.get_state.return_value = _state_response(json.loads(saved_value))
        self.assertEqual(
            self.store.read_completion(pipeline_id='p1', version='v1', document_id='doc-1'), record
        )

    def test_read_completion_returns_none_when_absent(self, _):
        self.assertIsNone(
            self.store.read_completion(pipeline_id='p1', version='v1', document_id='doc-1')
        )

    # -- embed progress -----------------------------------------------------

    def test_write_then_read_embed_progress_round_trips(self, _):
        record = EmbedProgressRecord(
            document_id='doc-1',
            source_content_hash='h1',
            pipeline_fingerprint='fp1',
            total_batches=2,
            completed_batch_indices=[0],
        )
        self.store.write_embed_progress(pipeline_id='p1', version='v1', record=record)
        saved_value = self.mock_client.save_state.call_args.kwargs['value']
        self.mock_client.get_state.return_value = _state_response(json.loads(saved_value))
        restored = self.store.read_embed_progress(
            pipeline_id='p1', version='v1', document_id='doc-1'
        )
        self.assertEqual(restored, record)

    # -- attempt counter -----------------------------------------------------

    def test_increment_attempt_count_starts_at_one_and_increments(self, _):
        first = self.store.increment_attempt_count(
            pipeline_id='p1', version='v1', document_id='doc-1'
        )
        self.assertEqual(first, 1)

        saved_value = self.mock_client.save_state.call_args.kwargs['value']
        self.mock_client.get_state.return_value = _state_response(json.loads(saved_value))
        second = self.store.increment_attempt_count(
            pipeline_id='p1', version='v1', document_id='doc-1'
        )
        self.assertEqual(second, 2)

    # -- status ---------------------------------------------------------

    def test_write_then_read_status_round_trips(self, _):
        status = PipelineStatus(
            pipeline_id='p1', requested_version='v1', workflow_instance_id='wf-1'
        )
        self.store.write_status(status)
        saved_value = self.mock_client.save_state.call_args.kwargs['value']
        self.mock_client.get_state.return_value = _state_response(json.loads(saved_value))
        self.assertEqual(self.store.read_status(pipeline_id='p1', version='v1'), status)

    # -- activation -----------------------------------------------------

    def test_read_activation_returns_none_and_the_etag_when_absent(self, _):
        self.mock_client.get_state.return_value = _state_response(None, etag='')
        record, etag = self.store.read_activation('p1')
        self.assertIsNone(record)
        self.assertEqual(etag, '')

    def test_read_activation_returns_the_record_and_etag_when_present(self, _):
        record = ActivationRecord(
            pipeline_id='p1',
            active_version='v1',
            previous_version=None,
            manifest_hash='h1',
            activated_at='2026-09-10T00:00:00+00:00',
            workflow_instance_id='wf-1',
        )
        self.mock_client.get_state.return_value = _state_response(record.to_dict(), etag='etag-1')
        restored, etag = self.store.read_activation('p1')
        self.assertEqual(restored, record)
        self.assertEqual(etag, 'etag-1')

    def test_write_activation_passes_the_etag_through(self, _):
        record = ActivationRecord(
            pipeline_id='p1',
            active_version='v1',
            previous_version=None,
            manifest_hash='h1',
            activated_at='2026-09-10T00:00:00+00:00',
            workflow_instance_id='wf-1',
        )
        self.store.write_activation(record, etag='etag-1')
        self.assertEqual(self.mock_client.save_state.call_args.kwargs['etag'], 'etag-1')

    def test_write_activation_raises_activation_conflict_on_aborted(self, _):
        self.mock_client.save_state.side_effect = _grpc_error(grpc.StatusCode.ABORTED)
        record = ActivationRecord(
            pipeline_id='p1',
            active_version='v1',
            previous_version=None,
            manifest_hash='h1',
            activated_at='2026-09-10T00:00:00+00:00',
            workflow_instance_id='wf-1',
        )
        with self.assertRaises(ActivationConflictError):
            self.store.write_activation(record, etag='stale-etag')

    def test_write_activation_reraises_unrelated_grpc_errors(self, _):
        self.mock_client.save_state.side_effect = _grpc_error(grpc.StatusCode.UNAVAILABLE)
        record = ActivationRecord(
            pipeline_id='p1',
            active_version='v1',
            previous_version=None,
            manifest_hash='h1',
            activated_at='2026-09-10T00:00:00+00:00',
            workflow_instance_id='wf-1',
        )
        with self.assertRaises(grpc.RpcError):
            self.store.write_activation(record, etag='etag-1')

    # -- lifecycle -----------------------------------------------------

    def test_close_only_closes_an_owned_client(self, mock_client_cls):
        owned_store = PipelineStateStore(state_store_name='statestore')
        owned_store.close()
        mock_client_cls.return_value.close.assert_called_once()

        self.store.close()
        self.mock_client.close.assert_not_called()


if __name__ == '__main__':
    unittest.main()
