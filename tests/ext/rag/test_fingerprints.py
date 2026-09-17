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

from dapr.ext.rag.fingerprints import (
    compute_chunk_id,
    compute_config_hash,
    compute_content_hash,
    compute_manifest_hash,
    compute_pipeline_fingerprint,
)


def _base_chunk_id_kwargs() -> dict:
    return dict(
        source_document_id='s3://bucket/doc.txt',
        source_content_hash='abc123',
        parser_config_hash='parser-hash',
        splitter_config_hash='splitter-hash',
        chunk_ordinal=0,
        chunk_content_hash='chunk-hash',
        embedding_model='text-embedding-3-small',
    )


class ComputeContentHashTest(unittest.TestCase):
    def test_deterministic(self):
        self.assertEqual(compute_content_hash(b'hello'), compute_content_hash(b'hello'))

    def test_sensitive_to_content(self):
        self.assertNotEqual(compute_content_hash(b'hello'), compute_content_hash(b'hellp'))

    def test_no_python_hash_randomization_dependency(self):
        # A regression guard: compute_content_hash must never delegate to Python's
        # process-randomized `hash()` for a persistent identity.
        digest = compute_content_hash(b'hello')
        self.assertEqual(len(digest), 64)  # hex sha256
        int(digest, 16)  # raises ValueError if it isn't hex


class ComputeConfigHashTest(unittest.TestCase):
    def test_stable_regardless_of_key_order(self):
        first = compute_config_hash({'a': 1, 'b': 2})
        second = compute_config_hash({'b': 2, 'a': 1})
        self.assertEqual(first, second)

    def test_sensitive_to_values(self):
        first = compute_config_hash({'chunk_size': 1000})
        second = compute_config_hash({'chunk_size': 1001})
        self.assertNotEqual(first, second)

    def test_sensitive_to_added_keys(self):
        first = compute_config_hash({'a': 1})
        second = compute_config_hash({'a': 1, 'b': None})
        self.assertNotEqual(first, second)


class ComputeChunkIdTest(unittest.TestCase):
    def test_deterministic_replay_produces_the_same_id(self):
        kwargs = _base_chunk_id_kwargs()
        self.assertEqual(compute_chunk_id(**kwargs), compute_chunk_id(**kwargs))

    def test_changing_any_single_field_changes_the_id(self):
        baseline = compute_chunk_id(**_base_chunk_id_kwargs())
        overrides = {
            'source_document_id': 's3://bucket/other.txt',
            'source_content_hash': 'different-content-hash',
            'parser_config_hash': 'different-parser-hash',
            'splitter_config_hash': 'different-splitter-hash',
            'chunk_ordinal': 1,
            'chunk_content_hash': 'different-chunk-hash',
            'embedding_model': 'text-embedding-3-large',
        }
        for field, new_value in overrides.items():
            with self.subTest(field=field):
                kwargs = _base_chunk_id_kwargs()
                kwargs[field] = new_value
                self.assertNotEqual(baseline, compute_chunk_id(**kwargs))

    def test_id_is_a_hex_sha256_digest(self):
        chunk_id = compute_chunk_id(**_base_chunk_id_kwargs())
        self.assertEqual(len(chunk_id), 64)
        int(chunk_id, 16)


class ComputeManifestHashTest(unittest.TestCase):
    def test_stable_regardless_of_listing_order(self):
        ids = ['doc-a', 'doc-b', 'doc-c']
        self.assertEqual(compute_manifest_hash(ids), compute_manifest_hash(reversed(ids)))

    def test_sensitive_to_membership(self):
        first = compute_manifest_hash(['doc-a', 'doc-b'])
        second = compute_manifest_hash(['doc-a', 'doc-c'])
        self.assertNotEqual(first, second)

    def test_empty_manifest_is_stable(self):
        self.assertEqual(compute_manifest_hash([]), compute_manifest_hash([]))


class ComputePipelineFingerprintTest(unittest.TestCase):
    def _base_kwargs(self) -> dict:
        return dict(
            parser_config_hash='parser-hash',
            splitter_config_hash='splitter-hash',
            embedding_model='text-embedding-3-small',
            embedding_config_hash='embed-hash',
        )

    def test_deterministic(self):
        kwargs = self._base_kwargs()
        self.assertEqual(
            compute_pipeline_fingerprint(**kwargs), compute_pipeline_fingerprint(**kwargs)
        )

    def test_changing_parser_config_changes_fingerprint(self):
        baseline = compute_pipeline_fingerprint(**self._base_kwargs())
        kwargs = self._base_kwargs()
        kwargs['parser_config_hash'] = 'different'
        self.assertNotEqual(baseline, compute_pipeline_fingerprint(**kwargs))

    def test_changing_splitter_config_changes_fingerprint(self):
        baseline = compute_pipeline_fingerprint(**self._base_kwargs())
        kwargs = self._base_kwargs()
        kwargs['splitter_config_hash'] = 'different'
        self.assertNotEqual(baseline, compute_pipeline_fingerprint(**kwargs))

    def test_changing_embedding_model_changes_fingerprint(self):
        baseline = compute_pipeline_fingerprint(**self._base_kwargs())
        kwargs = self._base_kwargs()
        kwargs['embedding_model'] = 'text-embedding-3-large'
        self.assertNotEqual(baseline, compute_pipeline_fingerprint(**kwargs))


if __name__ == '__main__':
    unittest.main()
