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

import datetime
import unittest
from unittest import mock

import boto3
from botocore.stub import Stubber

from dapr.ext.rag.errors import (
    OptionalDependencyError,
    SourceAccessDeniedError,
    SourceNotFoundError,
    TransientSourceError,
)
from dapr.ext.rag.models import SourceProvider
from dapr.ext.rag.sources.s3 import S3Source


def _client_and_stubber():
    client = boto3.client(
        's3',
        region_name='us-east-1',
        aws_access_key_id='test',
        aws_secret_access_key='test',
    )
    return client, Stubber(client)


class S3SourceConstructionTest(unittest.TestCase):
    def test_raises_optional_dependency_error_without_boto3_or_client(self):
        with mock.patch('dapr.ext.rag.sources.s3.boto3', None):
            with self.assertRaises(OptionalDependencyError):
                S3Source(bucket='company-docs')

    def test_client_injection_bypasses_the_dependency_check(self):
        client, _stubber = _client_and_stubber()
        with mock.patch('dapr.ext.rag.sources.s3.boto3', None):
            source = S3Source(bucket='company-docs', client=client)
        self.assertEqual(source.provider, SourceProvider.S3)


class S3SourceListDocumentsTest(unittest.TestCase):
    def test_paginates_across_multiple_pages(self):
        client, stubber = _client_and_stubber()
        last_modified = datetime.datetime(2026, 9, 1, tzinfo=datetime.timezone.utc)
        stubber.add_response(
            'list_objects_v2',
            {
                'Contents': [
                    {
                        'Key': 'policies/a.txt',
                        'ETag': '"etag-a"',
                        'Size': 10,
                        'LastModified': last_modified,
                    }
                ],
                'IsTruncated': True,
                'NextContinuationToken': 'token-1',
            },
            {'Bucket': 'company-docs', 'Prefix': 'policies/', 'MaxKeys': 1000},
        )
        stubber.add_response(
            'list_objects_v2',
            {
                'Contents': [
                    {
                        'Key': 'policies/b.txt',
                        'ETag': '"etag-b"',
                        'Size': 20,
                        'LastModified': last_modified,
                    }
                ],
                'IsTruncated': False,
            },
            {
                'Bucket': 'company-docs',
                'Prefix': 'policies/',
                'ContinuationToken': 'token-1',
                'MaxKeys': 1000,
            },
        )
        with stubber:
            source = S3Source(bucket='company-docs', prefix='policies/', client=client)
            documents = list(source.list_documents())

        self.assertEqual([d.name for d in documents], ['policies/a.txt', 'policies/b.txt'])
        self.assertEqual(documents[0].document_id, 's3://company-docs/policies/a.txt')
        self.assertEqual(documents[0].uri, documents[0].document_id)
        self.assertEqual(documents[0].provider, SourceProvider.S3)

    def test_normalizes_etag_and_last_modified(self):
        client, stubber = _client_and_stubber()
        last_modified = datetime.datetime(2026, 9, 1, 12, 0, tzinfo=datetime.timezone.utc)
        stubber.add_response(
            'list_objects_v2',
            {
                'Contents': [
                    {
                        'Key': 'a.txt',
                        'ETag': '"quoted-etag"',
                        'Size': 5,
                        'LastModified': last_modified,
                    }
                ],
                'IsTruncated': False,
            },
            {'Bucket': 'bucket', 'MaxKeys': 1000},
        )
        with stubber:
            source = S3Source(bucket='bucket', client=client)
            [document] = list(source.list_documents())

        self.assertEqual(document.metadata.etag, 'quoted-etag')  # quotes stripped
        self.assertEqual(document.metadata.content_length, 5)
        self.assertEqual(document.metadata.last_modified, last_modified.isoformat())

    def test_skips_zero_byte_directory_marker_objects(self):
        client, stubber = _client_and_stubber()
        stubber.add_response(
            'list_objects_v2',
            {
                'Contents': [
                    {'Key': 'policies/', 'ETag': '"dir"', 'Size': 0},
                    {'Key': 'policies/a.txt', 'ETag': '"a"', 'Size': 5},
                ],
                'IsTruncated': False,
            },
            {'Bucket': 'bucket', 'MaxKeys': 1000},
        )
        with stubber:
            source = S3Source(bucket='bucket', client=client)
            documents = list(source.list_documents())

        self.assertEqual([d.name for d in documents], ['policies/a.txt'])

    def test_call_level_prefix_overrides_the_configured_one(self):
        client, stubber = _client_and_stubber()
        stubber.add_response(
            'list_objects_v2',
            {'Contents': [], 'IsTruncated': False},
            {'Bucket': 'bucket', 'Prefix': 'override/', 'MaxKeys': 1000},
        )
        with stubber:
            source = S3Source(bucket='bucket', prefix='configured/', client=client)
            list(source.list_documents(prefix='override/'))
        stubber.assert_no_pending_responses()


class S3SourceGetDocumentTest(unittest.TestCase):
    def test_returns_the_object_body(self):
        client, stubber = _client_and_stubber()
        body = mock.Mock()
        body.read.return_value = b'hello world'
        stubber.add_response('get_object', {'Body': body}, {'Bucket': 'bucket', 'Key': 'a.txt'})
        with stubber:
            source = S3Source(bucket='bucket', client=client)
            content = source.get_document('s3://bucket/a.txt')
        self.assertEqual(content, b'hello world')

    def test_document_id_from_a_different_bucket_is_not_found(self):
        client, _stubber = _client_and_stubber()
        source = S3Source(bucket='bucket', client=client)
        with self.assertRaises(SourceNotFoundError):
            source.get_document('s3://other-bucket/a.txt')


class S3SourceGetMetadataTest(unittest.TestCase):
    def test_returns_normalized_metadata(self):
        client, stubber = _client_and_stubber()
        last_modified = datetime.datetime(2026, 9, 1, tzinfo=datetime.timezone.utc)
        stubber.add_response(
            'head_object',
            {
                'ETag': '"etag-1"',
                'VersionId': 'v1',
                'ContentLength': 42,
                'ContentType': 'text/plain',
                'LastModified': last_modified,
            },
            {'Bucket': 'bucket', 'Key': 'a.txt'},
        )
        with stubber:
            source = S3Source(bucket='bucket', client=client)
            metadata = source.get_metadata('s3://bucket/a.txt')

        self.assertEqual(metadata.etag, 'etag-1')
        self.assertEqual(metadata.version_id, 'v1')
        self.assertEqual(metadata.content_length, 42)
        self.assertEqual(metadata.content_type, 'text/plain')


class S3SourceErrorClassificationTest(unittest.TestCase):
    def test_missing_object_is_source_not_found(self):
        client, stubber = _client_and_stubber()
        stubber.add_client_error('get_object', service_error_code='NoSuchKey', http_status_code=404)
        with stubber:
            source = S3Source(bucket='bucket', client=client)
            with self.assertRaises(SourceNotFoundError):
                source.get_document('s3://bucket/a.txt')

    def test_access_denied_is_non_retryable(self):
        client, stubber = _client_and_stubber()
        stubber.add_client_error(
            'get_object', service_error_code='AccessDenied', http_status_code=403
        )
        with stubber:
            source = S3Source(bucket='bucket', client=client)
            with self.assertRaises(SourceAccessDeniedError):
                source.get_document('s3://bucket/a.txt')

    def test_throttling_is_transient(self):
        client, stubber = _client_and_stubber()
        stubber.add_client_error('get_object', service_error_code='SlowDown', http_status_code=503)
        with stubber:
            source = S3Source(bucket='bucket', client=client)
            with self.assertRaises(TransientSourceError):
                source.get_document('s3://bucket/a.txt')

    def test_unrecognized_5xx_is_transient(self):
        client, stubber = _client_and_stubber()
        stubber.add_client_error(
            'get_object', service_error_code='SomeNewError', http_status_code=500
        )
        with stubber:
            source = S3Source(bucket='bucket', client=client)
            with self.assertRaises(TransientSourceError):
                source.get_document('s3://bucket/a.txt')


if __name__ == '__main__':
    unittest.main()
