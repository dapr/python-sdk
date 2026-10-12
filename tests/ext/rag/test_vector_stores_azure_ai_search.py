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

import re
import unittest
from types import SimpleNamespace
from typing import Any
from unittest import mock

from dapr.ext.rag import vector_stores
from dapr.ext.rag.errors import OptionalDependencyError, TransientVectorStoreError, VectorStoreError
from dapr.ext.rag.models import VectorRecord
from dapr.ext.rag.vector_stores.azure_ai_search import AzureAISearchVectorStore

_HAS_REAL_SDK = vector_stores.azure_ai_search.SimpleField is not None


class ResourceNotFoundError(Exception):
    """Stands in for `azure.core.exceptions.ResourceNotFoundError` by class *name*
    (see azure_ai_search.py's `_is_not_found`) -- no azure-core dependency needed."""


class _FakeIndexingResult:
    def __init__(self, key, succeeded):
        self.key = key
        self.succeeded = succeeded


class _FakeSearchClient:
    def __init__(self, fail_keys_once=()):
        self.documents: dict[str, dict] = {}
        self.upload_calls: list[list[dict]] = []
        self._fail_keys_once = set(fail_keys_once)

    def merge_or_upload_documents(self, documents):
        self.upload_calls.append(documents)
        results = []
        for doc in documents:
            key = doc['id']
            if key in self._fail_keys_once:
                self._fail_keys_once.discard(key)
                results.append(_FakeIndexingResult(key, succeeded=False))
            else:
                self.documents[key] = doc
                results.append(_FakeIndexingResult(key, succeeded=True))
        return results

    def delete_documents(self, documents):
        for doc in documents:
            self.documents.pop(doc['id'], None)

    def get_document_count(self):
        return len(self.documents)

    def search(self, **kwargs):
        rows = []
        filter_expr = kwargs.get('filter')
        for doc in self.documents.values():
            if filter_expr and not _matches_filter(doc, filter_expr):
                continue
            row = dict(doc)
            row['@search.score'] = 0.87
            select = kwargs.get('select')
            if select:
                row = {k: v for k, v in row.items() if k in select or k.startswith('@search.')}
            rows.append(row)
        top = kwargs.get('top')
        return iter(rows[:top] if top else rows)

    def close(self):
        pass


def _matches_filter(doc, filter_expr):
    quoted = re.match(r"(\w+) eq '(.*)'$", filter_expr)
    if quoted:
        field, value = quoted.groups()
        return doc.get(field) == value.replace("''", "'")
    return True


class _FakeSearchIndexClient:
    def __init__(self, existing_index_names=()):
        self.indexes: dict[str, Any] = {
            name: SimpleNamespace(name=name, fields=[]) for name in existing_index_names
        }
        self.create_index_calls: list[Any] = []

    def get_index(self, name):
        if name not in self.indexes:
            raise ResourceNotFoundError(name)
        return self.indexes[name]

    def create_index(self, schema):
        self.create_index_calls.append(schema)
        self.indexes[schema.name] = schema

    def close(self):
        pass


class _FakeAliasResponse:
    def __init__(self, status_code, body=None):
        self.status_code = status_code
        self._body = body or {}
        self.text = str(self._body)

    def json(self):
        return self._body


class _FakeAliasTransport:
    """Stands in for `httpx.Client`, backed by the same `aliases`/`knowledge_sources` dicts
    a real REST-backed Search service would hold -- used for both alias switching and
    Foundry IQ knowledge-source registration, matching how one real transport serves both
    in `AzureAISearchVectorStore` (see its module comment)."""

    _ALIAS_NAME_PATTERN = re.compile(r"aliases\('([^']+)'\)")
    _KNOWLEDGE_SOURCE_NAME_PATTERN = re.compile(r"knowledgesources\('([^']+)'\)")

    def __init__(self, aliases, knowledge_sources=None):
        self._aliases = aliases
        self._knowledge_sources = knowledge_sources if knowledge_sources is not None else {}
        self.get_calls: list[str] = []
        self.put_calls: list[tuple] = []

    def get(self, url, headers=None):
        self.get_calls.append(url)
        alias_match = self._ALIAS_NAME_PATTERN.search(url)
        if alias_match:
            name = alias_match.group(1)
            if name not in self._aliases:
                return _FakeAliasResponse(404)
            return _FakeAliasResponse(200, {'name': name, 'indexes': self._aliases[name]})
        name = self._KNOWLEDGE_SOURCE_NAME_PATTERN.search(url).group(1)
        if name not in self._knowledge_sources:
            return _FakeAliasResponse(404)
        return _FakeAliasResponse(200, self._knowledge_sources[name])

    def put(self, url, headers=None, json=None):
        self.put_calls.append((url, json))
        if self._ALIAS_NAME_PATTERN.search(url):
            self._aliases[json['name']] = list(json['indexes'])
            return _FakeAliasResponse(
                200, {'name': json['name'], 'indexes': self._aliases[json['name']]}
            )
        self._knowledge_sources[json['name']] = json
        return _FakeAliasResponse(200, json)

    def close(self):
        pass


def _store(
    index_client=None, search_clients=None, aliases=None, knowledge_sources=None, **overrides
):
    index_client = index_client or _FakeSearchIndexClient(
        existing_index_names=['company-knowledge-2026-09']
    )
    search_clients = search_clients if search_clients is not None else {}
    aliases = aliases if aliases is not None else {}

    def factory(index_name):
        return search_clients.setdefault(index_name, _FakeSearchClient())

    kwargs = dict(
        endpoint='https://fake.search.windows.net',
        index_base_name='company-knowledge',
        index_client=index_client,
        search_client_factory=factory,
        alias_transport=_FakeAliasTransport(aliases, knowledge_sources),
    )
    kwargs.update(overrides)
    return AzureAISearchVectorStore(**kwargs), index_client, search_clients


def _record(chunk_id='c1', document_id='doc-1', content='hello', **metadata):
    return VectorRecord(
        chunk_id=chunk_id,
        document_id=document_id,
        content=content,
        embedding=[0.1, 0.2],
        metadata=metadata,
    )


class AzureAISearchVectorStoreConstructionTest(unittest.TestCase):
    def test_raises_optional_dependency_error_without_sdk_or_injection(self):
        with mock.patch('dapr.ext.rag.vector_stores.azure_ai_search.SearchIndexClient', None):
            with self.assertRaises(OptionalDependencyError):
                AzureAISearchVectorStore(
                    endpoint='https://x.search.windows.net', index_base_name='docs'
                )

    def test_requires_search_client_factory_alongside_index_client(self):
        with self.assertRaises(ValueError):
            AzureAISearchVectorStore(
                endpoint='https://fake.search.windows.net',
                index_base_name='docs',
                index_client=_FakeSearchIndexClient(),
                alias_transport=_FakeAliasTransport({}),
            )

    def test_alias_name_defaults_to_active_suffix(self):
        store, _client, _search = _store()
        self.assertEqual(store.alias_name, 'company-knowledge-active')

    def test_alias_name_can_be_overridden(self):
        store, _client, _search = _store(alias_name='company-knowledge-live')
        self.assertEqual(store.alias_name, 'company-knowledge-live')

    def test_store_type_and_target_index_name(self):
        store, _client, _search = _store()
        self.assertEqual(store.store_type, 'azure-ai-search')
        self.assertEqual(store.target_index_name, 'company-knowledge')


class AzureAISearchVectorStoreUpsertTest(unittest.TestCase):
    def test_upserts_into_the_version_specific_physical_index(self):
        store, _client, search_clients = _store()
        result = store.upsert([_record('c1')], version='2026-09')
        self.assertEqual(result.upserted_count, 1)
        self.assertIn('company-knowledge-2026-09', search_clients)
        self.assertIn('c1', search_clients['company-knowledge-2026-09'].documents)

    def test_upserting_the_same_chunk_id_twice_is_idempotent(self):
        store, _client, search_clients = _store()
        store.upsert([_record(content='v1')], version='2026-09')
        store.upsert([_record(content='v2')], version='2026-09')
        documents = search_clients['company-knowledge-2026-09'].documents
        self.assertEqual(len(documents), 1)
        self.assertEqual(documents['c1']['content'], 'v2')

    def test_empty_upsert_does_not_touch_the_search_client(self):
        store, _client, search_clients = _store()
        store.upsert([], version='2026-09')
        self.assertEqual(search_clients, {})

    def test_retries_only_the_batch_members_that_failed(self):
        search_client = _FakeSearchClient(fail_keys_once={'c2'})
        store, _client, _search = _store(
            search_clients={'company-knowledge-2026-09': search_client}
        )
        result = store.upsert([_record('c1'), _record('c2')], version='2026-09')
        self.assertEqual(result.upserted_count, 2)
        self.assertEqual(len(search_client.upload_calls), 2)
        self.assertEqual([doc['id'] for doc in search_client.upload_calls[1]], ['c2'])

    def test_raises_after_exhausting_batch_retries(self):
        search_client = _FakeSearchClient()
        search_client.merge_or_upload_documents = lambda documents: [
            _FakeIndexingResult(doc['id'], succeeded=False) for doc in documents
        ]
        store, _client, _search = _store(
            search_clients={'company-knowledge-2026-09': search_client}, max_batch_retries=2
        )
        with self.assertRaises(TransientVectorStoreError):
            store.upsert([_record('c1')], version='2026-09')

    def test_vector_field_is_not_returned_by_default_and_metadata_is_populated(self):
        store, _client, search_clients = _store()
        store.upsert(
            [
                _record(
                    'c1', document_id='doc-1', source_name='a.txt', pipeline_id='company-knowledge'
                )
            ],
            version='2026-09',
        )
        stored = search_clients['company-knowledge-2026-09'].documents['c1']
        self.assertIn('content_vector', stored)  # stored in the index...
        self.assertEqual(stored['title'], 'a.txt')
        self.assertEqual(stored['pipeline_id'], 'company-knowledge')


class AzureAISearchVectorStoreDeleteDocumentTest(unittest.TestCase):
    def test_deletes_only_matching_chunks(self):
        store, _client, search_clients = _store()
        store.upsert(
            [_record('c1', document_id='doc-1'), _record('c2', document_id='doc-2')],
            version='2026-09',
        )
        store.delete_document('doc-1', version='2026-09')
        documents = search_clients['company-knowledge-2026-09'].documents
        self.assertNotIn('c1', documents)
        self.assertIn('c2', documents)


class AzureAISearchVectorStoreValidateVersionTest(unittest.TestCase):
    def test_invalid_when_the_physical_index_does_not_exist(self):
        store, _client, _search = _store(index_client=_FakeSearchIndexClient())
        result = store.validate_version('2026-09')
        self.assertFalse(result.valid)
        self.assertEqual(result.actual_chunk_count, 0)

    def test_valid_once_documents_are_present(self):
        store, _client, _search = _store()
        store.upsert([_record('c1')], version='2026-09')
        result = store.validate_version('2026-09')
        self.assertTrue(result.valid)
        self.assertEqual(result.actual_chunk_count, 1)


class AzureAISearchVectorStoreActivateVersionTest(unittest.TestCase):
    """Alias switching goes through `_FakeAliasTransport` (a REST stand-in), never
    through `_FakeSearchIndexClient`, so these tests need no real SDK -- see the
    module comment in azure_ai_search.py on why aliases are REST-only."""

    def test_switches_the_alias_to_the_new_physical_index(self):
        aliases: dict[str, list[str]] = {}
        store, _client, _search = _store(aliases=aliases)
        store.activate_version('2026-09', previous_version=None)
        self.assertEqual(aliases['company-knowledge-active'], ['company-knowledge-2026-09'])

    def test_repeated_activation_of_the_same_version_does_not_switch_again(self):
        aliases: dict[str, list[str]] = {}
        index_client = _FakeSearchIndexClient(existing_index_names=['company-knowledge-2026-09'])
        alias_transport = _FakeAliasTransport(aliases)
        alias_transport.put = mock.Mock(wraps=alias_transport.put)
        store, _client, _search = _store(index_client=index_client, alias_transport=alias_transport)
        store.activate_version('2026-09', previous_version=None)
        store.activate_version('2026-09', previous_version=None)
        alias_transport.put.assert_called_once()

    def test_never_deletes_the_previous_index(self):
        aliases = {'company-knowledge-active': ['company-knowledge-2026-08']}
        index_client = _FakeSearchIndexClient(
            existing_index_names=['company-knowledge-2026-08', 'company-knowledge-2026-09']
        )
        store, _client, _search = _store(index_client=index_client, aliases=aliases)
        store.activate_version('2026-09', previous_version='2026-08')
        self.assertIn('company-knowledge-2026-08', index_client.indexes)

    def test_raises_transient_error_if_the_switch_never_becomes_observable(self):
        index_client = _FakeSearchIndexClient(existing_index_names=['company-knowledge-2026-09'])
        alias_transport = _FakeAliasTransport({})
        # The PUT itself succeeds, but never becomes visible to the following GETs
        # (e.g. eventual consistency) -- so the underlying dict is left untouched.
        alias_transport.put = mock.Mock(
            return_value=_FakeAliasResponse(200, {'name': 'x', 'indexes': []})
        )
        store, _client, _search = _store(
            index_client=index_client,
            alias_transport=alias_transport,
            alias_poll_attempts=2,
            alias_poll_interval_seconds=0.0,
        )
        with self.assertRaises(TransientVectorStoreError):
            store.activate_version('2026-09', previous_version=None)


class AzureAISearchVectorStoreFoundryIQKnowledgeSourceTest(unittest.TestCase):
    """Foundry IQ knowledge-source registration is REST-only for the same reason aliases
    are -- see azure_ai_search.py's module comment -- so these tests need no real SDK
    either, only `_FakeAliasTransport`."""

    def test_registers_a_new_knowledge_source_against_the_concrete_versioned_index(self):
        knowledge_sources: dict = {}
        store, _client, _search = _store(
            knowledge_sources=knowledge_sources, semantic_configuration_name='company-semantic'
        )
        store.register_foundry_iq_knowledge_source('2026-09', name='company-knowledge-ks')

        registered = knowledge_sources['company-knowledge-ks']
        self.assertEqual(registered['kind'], 'searchIndex')
        # The concrete physical index, never the alias -- see the method's docstring.
        self.assertEqual(
            registered['searchIndexParameters']['searchIndexName'], 'company-knowledge-2026-09'
        )
        self.assertEqual(
            registered['searchIndexParameters']['semanticConfigurationName'], 'company-semantic'
        )

    def test_requires_semantic_configuration_name_to_be_set(self):
        store, _client, _search = _store()  # no semantic_configuration_name
        with self.assertRaises(VectorStoreError):
            store.register_foundry_iq_knowledge_source('2026-09', name='company-knowledge-ks')

    def test_re_registering_the_same_version_is_a_no_op(self):
        knowledge_sources: dict = {}
        alias_transport = _FakeAliasTransport({}, knowledge_sources)
        alias_transport.put = mock.Mock(wraps=alias_transport.put)
        store, _client, _search = _store(
            alias_transport=alias_transport, semantic_configuration_name='company-semantic'
        )

        store.register_foundry_iq_knowledge_source('2026-09', name='company-knowledge-ks')
        store.register_foundry_iq_knowledge_source('2026-09', name='company-knowledge-ks')

        alias_transport.put.assert_called_once()

    def test_a_later_version_re_points_the_knowledge_source(self):
        knowledge_sources: dict = {}
        index_client = _FakeSearchIndexClient(
            existing_index_names=['company-knowledge-2026-08', 'company-knowledge-2026-09']
        )
        store, _client, _search = _store(
            index_client=index_client,
            knowledge_sources=knowledge_sources,
            semantic_configuration_name='company-semantic',
        )

        store.register_foundry_iq_knowledge_source('2026-08', name='company-knowledge-ks')
        store.register_foundry_iq_knowledge_source('2026-09', name='company-knowledge-ks')

        self.assertEqual(
            knowledge_sources['company-knowledge-ks']['searchIndexParameters']['searchIndexName'],
            'company-knowledge-2026-09',
        )

    def test_source_data_fields_and_search_fields_are_passed_through(self):
        knowledge_sources: dict = {}
        store, _client, _search = _store(
            knowledge_sources=knowledge_sources, semantic_configuration_name='company-semantic'
        )
        store.register_foundry_iq_knowledge_source(
            '2026-09',
            name='company-knowledge-ks',
            source_data_fields=['title', 'source_uri'],
            search_fields=['content'],
        )

        params = knowledge_sources['company-knowledge-ks']['searchIndexParameters']
        self.assertEqual(params['sourceDataFields'], [{'name': 'title'}, {'name': 'source_uri'}])
        self.assertEqual(params['searchFields'], [{'name': 'content'}])


@unittest.skipUnless(
    _HAS_REAL_SDK, 'requires azure-search-documents: query() constructs a real VectorizedQuery'
)
class AzureAISearchVectorStoreQueryTest(unittest.TestCase):
    def test_hybrid_query_returns_matches_excluding_the_vector_field(self):
        store, _client, _search = _store()
        store.upsert([_record('c1', document_id='doc-1', content='hello world')], version='2026-09')
        [match] = store.query([0.1, 0.2], version='2026-09', query_text='hello', top_k=5)
        self.assertEqual(match.chunk_id, 'c1')
        self.assertEqual(match.document_id, 'doc-1')
        self.assertEqual(match.content, 'hello world')
        self.assertNotIn('content_vector', match.metadata)

    def test_metadata_filter_is_applied(self):
        store, _client, search_clients = _store()
        store.upsert(
            [_record('c1', document_id='doc-1'), _record('c2', document_id='doc-2')],
            version='2026-09',
        )
        matches = store.query(
            [0.1], version='2026-09', metadata_filter={'source_document_id': 'doc-1'}
        )
        self.assertEqual([m.chunk_id for m in matches], ['c1'])


@unittest.skipUnless(_HAS_REAL_SDK, 'requires azure-search-documents for real schema model classes')
class AzureAISearchVectorStoreSchemaCreationTest(unittest.TestCase):
    def test_creates_a_new_index_with_a_vector_field_sized_to_the_embedding(self):
        index_client = _FakeSearchIndexClient()  # no pre-existing indexes
        store, _client, _search = _store(index_client=index_client)
        store.upsert([_record('c1')], version='2026-09')  # embedding is 2-dimensional
        [schema] = index_client.create_index_calls
        vector_field = next(f for f in schema.fields if f.name == 'content_vector')
        self.assertEqual(vector_field.vector_search_dimensions, 2)

    def test_rejects_a_dimension_mismatch_against_an_existing_index(self):
        index_client = _FakeSearchIndexClient()
        store, _client, _search = _store(index_client=index_client, vector_dimensions=2)
        store.upsert([_record('c1')], version='2026-09')  # creates with dimensions=2

        other_store, _client2, _search2 = _store(index_client=index_client, vector_dimensions=1536)
        with self.assertRaises(VectorStoreError):
            other_store.upsert([_record('c2')], version='2026-09')


if __name__ == '__main__':
    unittest.main()
