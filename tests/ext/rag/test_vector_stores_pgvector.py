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

from dapr.ext.rag.errors import OptionalDependencyError
from dapr.ext.rag.models import VectorRecord
from dapr.ext.rag.vector_stores.pgvector import PgVectorStore


class _FakeCursor:
    """Interprets just enough of PgVectorStore's own SQL to fake a tiny database.

    This intentionally couples to PgVectorStore's own query shapes (a real
    Postgres+pgvector round trip belongs in the optional integration profile,
    not here) -- it verifies *this class's* control flow: upsert is
    idempotent by (version, chunk_id), schema is created once, and
    validate_version/query reflect what was written.
    """

    def __init__(self, tables, executed):
        self._tables = tables
        self._executed = executed
        self._result_one = None
        self._result_many = []

    def execute(self, sql, params=()):
        self._executed.append((' '.join(sql.split()), tuple(params)))
        normalized = ' '.join(sql.split())
        if normalized.startswith('CREATE TABLE'):
            table = normalized.split()[5]
            self._tables.setdefault(table, {})
        elif normalized.startswith('INSERT INTO'):
            table = normalized.split()[2]
            chunk_id, version, document_id, content, _embedding, metadata_json = params
            self._tables.setdefault(table, {})[(version, chunk_id)] = {
                'document_id': document_id,
                'content': content,
                'metadata': json.loads(metadata_json),
            }
        elif normalized.startswith('DELETE FROM'):
            table = normalized.split()[2]
            version, document_id = params
            rows = self._tables.get(table, {})
            for key in [
                k for k, v in rows.items() if k[0] == version and v['document_id'] == document_id
            ]:
                del rows[key]
        elif 'SELECT COUNT(*), COUNT(DISTINCT document_id)' in normalized:
            table = normalized.split()[normalized.split().index('FROM') + 1]
            (version,) = params
            rows = [v for k, v in self._tables.get(table, {}).items() if k[0] == version]
            self._result_one = (len(rows), len({r['document_id'] for r in rows}))
        elif normalized.startswith('SELECT chunk_id'):
            table = normalized.split()[normalized.split().index('FROM') + 1]
            # execute()'s params are [vector_literal, version, (metadata_json,)
            # vector_literal, top_k] -- see PgVectorStore.query -- so version is
            # the second positional parameter, not the first.
            version = params[1]
            rows = [
                (chunk_id, v['document_id'], v['content'], v['metadata'], 0.99)
                for (row_version, chunk_id), v in self._tables.get(table, {}).items()
                if row_version == version
            ]
            self._result_many = rows

    def fetchone(self):
        return self._result_one

    def fetchall(self):
        return self._result_many

    def __enter__(self):
        return self

    def __exit__(self, *exc_info):
        return False


class _FakeConnection:
    def __init__(self, tables, executed):
        self._tables = tables
        self._executed = executed
        self.commits = 0
        self.rollbacks = 0

    def cursor(self):
        return _FakeCursor(self._tables, self._executed)

    def commit(self):
        self.commits += 1

    def rollback(self):
        self.rollbacks += 1

    def __enter__(self):
        return self

    def __exit__(self, *exc_info):
        return False


def _store(tables=None, executed=None):
    tables = tables if tables is not None else {}
    executed = executed if executed is not None else []
    factory = lambda: _FakeConnection(tables, executed)  # noqa: E731
    return (
        PgVectorStore(collection='company_knowledge', connection_factory=factory),
        tables,
        executed,
    )


def _record(chunk_id='chunk-1', document_id='doc-1', content='hello'):
    return VectorRecord(
        chunk_id=chunk_id, document_id=document_id, content=content, embedding=[0.1, 0.2]
    )


class PgVectorStoreConstructionTest(unittest.TestCase):
    def test_raises_optional_dependency_error_without_psycopg_or_connection_factory(self):
        with mock.patch('dapr.ext.rag.vector_stores.pgvector.psycopg', None):
            with self.assertRaises(OptionalDependencyError):
                PgVectorStore(connection_string='postgresql://x', collection='docs')

    def test_rejects_an_unsafe_collection_name(self):
        with self.assertRaises(ValueError):
            PgVectorStore(
                collection='not a safe identifier; DROP TABLE x;--', connection_factory=lambda: None
            )

    def test_requires_connection_string_or_factory(self):
        with mock.patch('dapr.ext.rag.vector_stores.pgvector.psycopg', mock.Mock()):
            with self.assertRaises(ValueError):
                PgVectorStore(collection='docs')


class PgVectorStoreUpsertTest(unittest.TestCase):
    def test_upserting_the_same_chunk_id_twice_is_idempotent(self):
        store, tables, _executed = _store()
        store.upsert([_record(content='v1')], version='2026-09')
        store.upsert([_record(content='v2')], version='2026-09')

        table_rows = next(iter(tables.values()))
        self.assertEqual(len(table_rows), 1)
        self.assertEqual(table_rows[('2026-09', 'chunk-1')]['content'], 'v2')

    def test_upsert_result_reports_the_record_count(self):
        store, _tables, _executed = _store()
        result = store.upsert([_record('c1'), _record('c2')], version='2026-09')
        self.assertEqual(result.upserted_count, 2)
        self.assertEqual(result.version, '2026-09')

    def test_empty_upsert_does_not_touch_the_connection(self):
        store, _tables, executed = _store()
        store.upsert([], version='2026-09')
        self.assertEqual(executed, [])

    def test_schema_is_created_only_once_across_multiple_upserts(self):
        store, _tables, executed = _store()
        store.upsert([_record('c1')], version='2026-09')
        store.upsert([_record('c2')], version='2026-09')
        create_table_calls = [sql for sql, _params in executed if sql.startswith('CREATE TABLE')]
        self.assertEqual(len(create_table_calls), 1)

    def test_different_versions_are_isolated(self):
        store, _tables, _executed = _store()
        store.upsert([_record('c1', document_id='doc-1')], version='2026-08')
        store.upsert([_record('c1', document_id='doc-1')], version='2026-09')
        result_08 = store.validate_version('2026-08')
        result_09 = store.validate_version('2026-09')
        self.assertEqual(result_08.actual_chunk_count, 1)
        self.assertEqual(result_09.actual_chunk_count, 1)


class PgVectorStoreDeleteDocumentTest(unittest.TestCase):
    def test_deletes_only_chunks_for_the_given_document_and_version(self):
        store, _tables, _executed = _store()
        store.upsert(
            [_record('c1', document_id='doc-1'), _record('c2', document_id='doc-2')],
            version='2026-09',
        )
        store.delete_document('doc-1', version='2026-09')
        result = store.validate_version('2026-09')
        self.assertEqual(result.actual_chunk_count, 1)
        self.assertEqual(result.actual_document_count, 1)


class PgVectorStoreValidateVersionTest(unittest.TestCase):
    def test_reports_zero_for_an_empty_version(self):
        store, _tables, _executed = _store()
        result = store.validate_version('2026-09')
        self.assertEqual(result.actual_chunk_count, 0)
        self.assertEqual(result.actual_document_count, 0)
        self.assertFalse(
            result.valid
        )  # base VectorIndex-level default; pipeline recomputes `valid`

    def test_reports_accurate_counts(self):
        store, _tables, _executed = _store()
        store.upsert(
            [
                _record('c1', document_id='doc-1'),
                _record('c2', document_id='doc-1'),
                _record('c3', document_id='doc-2'),
            ],
            version='2026-09',
        )
        result = store.validate_version('2026-09')
        self.assertEqual(result.actual_chunk_count, 3)
        self.assertEqual(result.actual_document_count, 2)


class PgVectorStoreQueryTest(unittest.TestCase):
    def test_returns_query_matches_from_the_stored_rows(self):
        store, _tables, _executed = _store()
        store.upsert([_record('c1', document_id='doc-1', content='hello world')], version='2026-09')
        matches = store.query([0.1, 0.2], version='2026-09', top_k=5)
        self.assertEqual(len(matches), 1)
        self.assertEqual(matches[0].chunk_id, 'c1')
        self.assertEqual(matches[0].document_id, 'doc-1')
        self.assertEqual(matches[0].content, 'hello world')

    def test_metadata_filter_adds_a_where_clause(self):
        store, _tables, executed = _store()
        store.query([0.1, 0.2], version='2026-09', metadata_filter={'document_id': 'doc-1'})
        select_calls = [sql for sql, _params in executed if sql.startswith('SELECT chunk_id')]
        self.assertIn('metadata @>', select_calls[0])


if __name__ == '__main__':
    unittest.main()
