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

from dapr.ext.rag.errors import VersionValidationError
from dapr.ext.rag.models import ActivationRecord, EmbeddingBatchResult, QueryMatch
from dapr.ext.rag.retrieval import ActiveVersionResolver


def _state_response(value):
    response = mock.Mock()
    response.data = None if value is None else json.dumps(value).encode('utf-8')
    response.etag = 'etag-1'
    return response


class ActiveVersionResolverTest(unittest.TestCase):
    def setUp(self):
        self.dapr_client = mock.Mock()
        self.embedder = mock.Mock()
        self.vector_store = mock.Mock()
        self.resolver = ActiveVersionResolver(
            pipeline_id='company-knowledge',
            state_store_name='statestore',
            vector_store=self.vector_store,
            embedder=self.embedder,
            dapr_client=self.dapr_client,
        )

    def _activate(self, version, previous_version=None):
        record = ActivationRecord(
            pipeline_id='company-knowledge',
            active_version=version,
            previous_version=previous_version,
            manifest_hash='hash',
            activated_at='2026-09-10T00:00:00+00:00',
            workflow_instance_id='wf-1',
        )
        self.dapr_client.get_state.return_value = _state_response(record.to_dict())

    def test_resolve_active_version_returns_none_before_any_activation(self):
        self.dapr_client.get_state.return_value = _state_response(None)
        self.assertIsNone(self.resolver.resolve_active_version())

    def test_resolve_active_version_returns_the_active_version(self):
        self._activate('2026-09')
        self.assertEqual(self.resolver.resolve_active_version(), '2026-09')

    def test_query_raises_when_no_version_has_ever_been_activated(self):
        self.dapr_client.get_state.return_value = _state_response(None)
        with self.assertRaises(VersionValidationError):
            self.resolver.query('what is the policy?')

    def test_query_embeds_the_text_and_searches_only_the_active_version(self):
        self._activate('2026-09')
        self.embedder.embed_batch.return_value = EmbeddingBatchResult(embeddings=[[0.1, 0.2]])
        expected = [QueryMatch(chunk_id='c1', document_id='doc-1', content='hello', score=0.9)]
        self.vector_store.query.return_value = expected

        results = self.resolver.query('what is the policy?', top_k=3)

        self.embedder.embed_batch.assert_called_once_with(['what is the policy?'])
        self.vector_store.query.assert_called_once_with(
            [0.1, 0.2], '2026-09', top_k=3, metadata_filter=None, query_text='what is the policy?'
        )
        self.assertEqual(results, expected)

    def test_query_does_not_search_a_version_still_being_built(self):
        # Only ever activated '2026-08'; a '2026-09' build in progress must not be
        # visible here even though it may already have vectors written.
        self._activate('2026-08')
        self.embedder.embed_batch.return_value = EmbeddingBatchResult(embeddings=[[0.1]])
        self.resolver.query('question')
        self.assertEqual(self.vector_store.query.call_args.args[1], '2026-08')

    def test_close_closes_the_underlying_state_store(self):
        with mock.patch.object(self.resolver, '_state') as mock_state:
            self.resolver.close()
            mock_state.close.assert_called_once()


if __name__ == '__main__':
    unittest.main()
