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

from dapr.ext.rag.models import (
    ActivationRecord,
    CompletionRecord,
    DocumentFailure,
    DocumentWorkItem,
    EmbedProgressRecord,
    PipelineConfig,
    PipelineStatus,
    SourceDocument,
    SourceMetadata,
    SourceProvider,
)


class PipelineConfigTest(unittest.TestCase):
    def test_defaults_match_the_documented_values(self):
        config = PipelineConfig()
        self.assertEqual(config.max_concurrent_documents, 10)
        self.assertEqual(config.embedding_batch_size, 64)
        self.assertEqual(config.max_activity_attempts, 5)
        self.assertFalse(config.fail_fast)

    def test_effective_manifest_page_size_defaults_to_max_concurrent_documents(self):
        config = PipelineConfig(max_concurrent_documents=7)
        self.assertEqual(config.effective_manifest_page_size, 7)

    def test_effective_manifest_page_size_honors_explicit_override(self):
        config = PipelineConfig(max_concurrent_documents=7, manifest_page_size=25)
        self.assertEqual(config.effective_manifest_page_size, 25)

    def test_rejects_non_positive_max_concurrent_documents(self):
        with self.assertRaises(ValueError):
            PipelineConfig(max_concurrent_documents=0)

    def test_rejects_non_positive_embedding_batch_size(self):
        with self.assertRaises(ValueError):
            PipelineConfig(embedding_batch_size=0)

    def test_rejects_non_positive_max_activity_attempts(self):
        with self.assertRaises(ValueError):
            PipelineConfig(max_activity_attempts=0)

    def test_round_trips_through_to_dict_and_from_dict(self):
        config = PipelineConfig(max_concurrent_documents=3, fail_fast=True)
        self.assertEqual(PipelineConfig.from_dict(config.to_dict()), config)


class DocumentWorkItemTest(unittest.TestCase):
    def test_from_source_document_flattens_nested_metadata(self):
        doc = SourceDocument(
            document_id='s3://bucket/a.txt',
            provider=SourceProvider.S3,
            uri='s3://bucket/a.txt',
            name='a.txt',
            metadata=SourceMetadata(etag='etag-1', version_id='v1', content_length=42),
        )
        item = DocumentWorkItem.from_source_document(doc)
        self.assertEqual(
            item,
            DocumentWorkItem(
                document_id='s3://bucket/a.txt',
                provider='s3',
                uri='s3://bucket/a.txt',
                name='a.txt',
                source_etag='etag-1',
                source_version_id='v1',
                source_content_length=42,
            ),
        )


class ActivationRecordTest(unittest.TestCase):
    def test_round_trips_through_to_dict_and_from_dict(self):
        record = ActivationRecord(
            pipeline_id='company-knowledge',
            active_version='2026-09',
            previous_version='2026-08',
            manifest_hash='abc',
            activated_at='2026-09-10T00:00:00+00:00',
            workflow_instance_id='wf-1',
        )
        self.assertEqual(ActivationRecord.from_dict(record.to_dict()), record)


class CompletionRecordTest(unittest.TestCase):
    def test_round_trips_through_to_dict_and_from_dict(self):
        record = CompletionRecord(
            document_id='doc-1',
            source_content_hash='hash-1',
            pipeline_fingerprint='fp-1',
            chunk_count=3,
            embedded_chunk_count=3,
            completed_at='2026-09-10T00:00:00+00:00',
        )
        self.assertEqual(CompletionRecord.from_dict(record.to_dict()), record)


class EmbedProgressRecordTest(unittest.TestCase):
    def test_round_trips_including_completed_batch_indices(self):
        record = EmbedProgressRecord(
            document_id='doc-1',
            source_content_hash='hash-1',
            pipeline_fingerprint='fp-1',
            total_batches=3,
            completed_batch_indices=[0, 1],
        )
        restored = EmbedProgressRecord.from_dict(record.to_dict())
        self.assertEqual(restored, record)
        self.assertEqual(restored.completed_batch_indices, [0, 1])


class PipelineStatusTest(unittest.TestCase):
    def test_round_trips_including_nested_failures(self):
        status = PipelineStatus(
            pipeline_id='company-knowledge',
            requested_version='2026-09',
            workflow_instance_id='wf-1',
            failed_documents=1,
            failures=(
                DocumentFailure(
                    document_id='doc-1',
                    error_type='DocumentParseError',
                    error_message='corrupt',
                    retryable=False,
                ),
            ),
        )
        restored = PipelineStatus.from_dict(status.to_dict())
        self.assertEqual(restored, status)
        self.assertIsInstance(restored.failures[0], DocumentFailure)

    def test_from_dict_defaults_missing_failures_to_empty(self):
        status = PipelineStatus(pipeline_id='p', requested_version='v', workflow_instance_id='wf-1')
        payload = status.to_dict()
        del payload['failures']
        restored = PipelineStatus.from_dict(payload)
        self.assertEqual(restored.failures, ())


if __name__ == '__main__':
    unittest.main()
