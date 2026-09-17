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

import unittest
from types import SimpleNamespace
from unittest import mock

from dapr.ext.rag.errors import OptionalDependencyError, TransientVectorStoreError, VectorStoreError
from dapr.ext.rag.models import VectorRecord
from dapr.ext.rag.vector_stores.pinecone import PineconeVectorStore


class _FakeIndex:
    def __init__(self, describe_exception=None, delete_exception=None):
        self.upsert_calls = []
        self.delete_calls = []
        self._namespaces = {}
        self._describe_exception = describe_exception
        self._delete_exception = delete_exception

    def upsert(self, vectors, namespace):
        self.upsert_calls.append({'vectors': vectors, 'namespace': namespace})
        store = self._namespaces.setdefault(namespace, {})
        for vector in vectors:
            store[vector['id']] = vector

    def delete(self, namespace, filter=None, ids=None):
        self.delete_calls.append({'filter': filter, 'ids': ids, 'namespace': namespace})
        if self._delete_exception is not None:
            raise self._delete_exception
        store = self._namespaces.get(namespace, {})
        if filter and 'document_id' in filter:
            doc_id = filter['document_id']['$eq']
            for vector_id in [
                vid for vid, v in store.items() if v['metadata'].get('document_id') == doc_id
            ]:
                del store[vector_id]

    def describe_index_stats(self):
        if self._describe_exception is not None:
            raise self._describe_exception
        return SimpleNamespace(
            namespaces={
                ns: SimpleNamespace(vector_count=len(vectors))
                for ns, vectors in self._namespaces.items()
            }
        )

    def query(self, vector, top_k, namespace, include_metadata, filter=None):
        store = self._namespaces.get(namespace, {})
        matches = [
            SimpleNamespace(id=vector_id, score=0.9, metadata=v['metadata'])
            for vector_id, v in list(store.items())[:top_k]
        ]
        return SimpleNamespace(matches=matches)


def _record(chunk_id='c1', document_id='doc-1', content='hello'):
    return VectorRecord(
        chunk_id=chunk_id, document_id=document_id, content=content, embedding=[0.1, 0.2]
    )


def _fake_error(name, status=None):
    error_cls = type(name, (Exception,), {})
    error = error_cls('boom')
    if status is not None:
        error.status = status
    return error


class PineconeVectorStoreConstructionTest(unittest.TestCase):
    def test_raises_optional_dependency_error_without_pinecone_or_client(self):
        with mock.patch('dapr.ext.rag.vector_stores.pinecone.Pinecone', None):
            with self.assertRaises(OptionalDependencyError):
                PineconeVectorStore(index_name='company-knowledge')

    def test_client_injection_bypasses_the_dependency_check(self):
        with mock.patch('dapr.ext.rag.vector_stores.pinecone.Pinecone', None):
            store = PineconeVectorStore(index_name='company-knowledge', client=_FakeIndex())
        self.assertEqual(store.store_type, 'pinecone')
        self.assertEqual(store.target_index_name, 'company-knowledge')


class PineconeVectorStoreUpsertTest(unittest.TestCase):
    def test_batches_upserts_according_to_batch_size(self):
        index = _FakeIndex()
        store = PineconeVectorStore(index_name='idx', batch_size=2, client=index)
        store.upsert([_record('c1'), _record('c2'), _record('c3')], version='2026-09')
        self.assertEqual(len(index.upsert_calls), 2)
        self.assertEqual(len(index.upsert_calls[0]['vectors']), 2)
        self.assertEqual(len(index.upsert_calls[1]['vectors']), 1)

    def test_upserting_the_same_chunk_id_twice_is_idempotent(self):
        index = _FakeIndex()
        store = PineconeVectorStore(index_name='idx', client=index)
        store.upsert([_record(content='v1')], version='2026-09')
        store.upsert([_record(content='v2')], version='2026-09')
        self.assertEqual(len(index._namespaces['2026-09']), 1)
        self.assertEqual(index._namespaces['2026-09']['c1']['metadata']['content'], 'v2')

    def test_vector_metadata_includes_document_id_and_content(self):
        index = _FakeIndex()
        store = PineconeVectorStore(index_name='idx', client=index)
        store.upsert([_record(document_id='doc-1', content='hello')], version='2026-09')
        vector = index.upsert_calls[0]['vectors'][0]
        self.assertEqual(vector['metadata']['document_id'], 'doc-1')
        self.assertEqual(vector['metadata']['content'], 'hello')

    def test_empty_upsert_does_not_call_the_index(self):
        index = _FakeIndex()
        store = PineconeVectorStore(index_name='idx', client=index)
        store.upsert([], version='2026-09')
        self.assertEqual(index.upsert_calls, [])

    def test_upsert_uses_version_as_namespace(self):
        index = _FakeIndex()
        store = PineconeVectorStore(index_name='idx', client=index)
        store.upsert([_record()], version='2026-09')
        self.assertEqual(index.upsert_calls[0]['namespace'], '2026-09')


class PineconeVectorStoreDeleteDocumentTest(unittest.TestCase):
    def test_deletes_only_matching_document(self):
        index = _FakeIndex()
        store = PineconeVectorStore(index_name='idx', client=index)
        store.upsert(
            [_record('c1', document_id='doc-1'), _record('c2', document_id='doc-2')], version='v1'
        )
        store.delete_document('doc-1', version='v1')
        self.assertNotIn('c1', index._namespaces['v1'])
        self.assertIn('c2', index._namespaces['v1'])

    def test_serverless_limitation_becomes_a_clear_vector_store_error(self):
        index = _FakeIndex(
            delete_exception=RuntimeError('operation not supported on Serverless index')
        )
        store = PineconeVectorStore(index_name='idx', client=index)
        with self.assertRaises(VectorStoreError):
            store.delete_document('doc-1', version='v1')


class PineconeVectorStoreValidateVersionTest(unittest.TestCase):
    def test_reports_the_namespace_vector_count(self):
        index = _FakeIndex()
        store = PineconeVectorStore(index_name='idx', client=index)
        store.upsert([_record('c1'), _record('c2')], version='v1')
        result = store.validate_version('v1')
        self.assertEqual(result.actual_chunk_count, 2)
        self.assertTrue(result.valid)

    def test_missing_namespace_reports_zero(self):
        store = PineconeVectorStore(index_name='idx', client=_FakeIndex())
        result = store.validate_version('never-built')
        self.assertEqual(result.actual_chunk_count, 0)
        self.assertFalse(result.valid)

    def test_handles_dict_shaped_stats_response(self):
        index = _FakeIndex()
        index.describe_index_stats = lambda: {'namespaces': {'v1': {'vector_count': 5}}}
        store = PineconeVectorStore(index_name='idx', client=index)
        result = store.validate_version('v1')
        self.assertEqual(result.actual_chunk_count, 5)


class PineconeVectorStoreQueryTest(unittest.TestCase):
    def test_extracts_document_id_and_content_from_metadata(self):
        index = _FakeIndex()
        store = PineconeVectorStore(index_name='idx', client=index)
        store.upsert([_record(document_id='doc-1', content='hello world')], version='v1')
        [match] = store.query([0.1, 0.2], version='v1', top_k=1)
        self.assertEqual(match.chunk_id, 'c1')
        self.assertEqual(match.document_id, 'doc-1')
        self.assertEqual(match.content, 'hello world')
        self.assertNotIn('document_id', match.metadata)  # popped out into its own field
        self.assertNotIn('content', match.metadata)


class PineconeVectorStoreErrorClassificationTest(unittest.TestCase):
    def test_named_transient_exception_is_transient(self):
        index = _FakeIndex(describe_exception=_fake_error('PineconeApiException'))
        store = PineconeVectorStore(index_name='idx', client=index)
        with self.assertRaises(TransientVectorStoreError):
            store.validate_version('v1')

    def test_5xx_status_is_transient(self):
        index = _FakeIndex(describe_exception=_fake_error('SomeError', status=503))
        store = PineconeVectorStore(index_name='idx', client=index)
        with self.assertRaises(TransientVectorStoreError):
            store.validate_version('v1')

    def test_unrecognized_failure_is_a_plain_vector_store_error(self):
        index = _FakeIndex(describe_exception=_fake_error('SomeConfigError'))
        store = PineconeVectorStore(index_name='idx', client=index)
        with self.assertRaises(VectorStoreError):
            store.validate_version('v1')


if __name__ == '__main__':
    unittest.main()
