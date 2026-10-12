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
from types import SimpleNamespace
from unittest import mock

from dapr.ext.rag.errors import (
    OptionalDependencyError,
    SourceAccessDeniedError,
    SourceNotFoundError,
    TransientSourceError,
)
from dapr.ext.rag.models import SourceProvider
from dapr.ext.rag.sources.azure_blob import AzureBlobSource


class _FakeBlob:
    def __init__(
        self, name, etag=None, last_modified=None, size=None, content_type=None, deleted=False
    ):
        self.name = name
        self.etag = etag
        self.last_modified = last_modified
        self.size = size
        self.content_settings = SimpleNamespace(content_type=content_type)
        self.version_id = None
        self.deleted = deleted


class _FakeDownloader:
    def __init__(self, data):
        self._data = data

    def readall(self):
        return self._data


class _FakeBlobClient:
    def __init__(self, properties):
        self._properties = properties

    def get_blob_properties(self):
        return self._properties


class _FakeContainerClient:
    def __init__(
        self, account_name='myaccount', blobs=(), downloads=None, properties=None, exception=None
    ):
        self.account_name = account_name
        self._blobs = list(blobs)
        self._downloads = downloads or {}
        self._properties = properties or {}
        self._exception = exception
        self.list_calls = []

    def list_blobs(self, name_starts_with=None, results_per_page=None):
        self.list_calls.append(
            {'name_starts_with': name_starts_with, 'results_per_page': results_per_page}
        )
        if self._exception is not None:
            raise self._exception
        return iter(self._blobs)

    def download_blob(self, blob_name):
        if self._exception is not None:
            raise self._exception
        return _FakeDownloader(self._downloads[blob_name])

    def get_blob_client(self, blob_name):
        if self._exception is not None:
            raise self._exception
        return _FakeBlobClient(self._properties[blob_name])


def _fake_error(name, status_code=None):
    error_cls = type(name, (Exception,), {})
    error = error_cls('boom')
    if status_code is not None:
        error.status_code = status_code
    return error


class AzureBlobSourceConstructionTest(unittest.TestCase):
    def test_raises_optional_dependency_error_without_azure_sdk_or_client(self):
        with mock.patch('dapr.ext.rag.sources.azure_blob.BlobServiceClient', None):
            with self.assertRaises(OptionalDependencyError) as ctx:
                AzureBlobSource(account_url='https://x.blob.core.windows.net', container='docs')
        self.assertEqual(ctx.exception.package, 'azure-storage-blob')

    def test_raises_optional_dependency_error_for_missing_azure_identity(self):
        fake_service_client_cls = mock.Mock()
        with mock.patch(
            'dapr.ext.rag.sources.azure_blob.BlobServiceClient', fake_service_client_cls
        ):
            with mock.patch('dapr.ext.rag.sources.azure_blob.DefaultAzureCredential', None):
                with self.assertRaises(OptionalDependencyError) as ctx:
                    AzureBlobSource(account_url='https://x.blob.core.windows.net', container='docs')
        self.assertEqual(ctx.exception.package, 'azure-identity')

    def test_requires_account_url_connection_string_or_client(self):
        fake_service_client_cls = mock.Mock()
        with mock.patch(
            'dapr.ext.rag.sources.azure_blob.BlobServiceClient', fake_service_client_cls
        ):
            with self.assertRaises(ValueError):
                AzureBlobSource(container='docs')

    def test_client_injection_bypasses_the_dependency_check(self):
        with mock.patch('dapr.ext.rag.sources.azure_blob.BlobServiceClient', None):
            source = AzureBlobSource(container='docs', client=_FakeContainerClient())
        self.assertEqual(source.provider, SourceProvider.AZURE_BLOB)


class AzureBlobSourceListDocumentsTest(unittest.TestCase):
    def test_normalizes_blobs_into_source_documents(self):
        last_modified = datetime.datetime(2026, 9, 1, tzinfo=datetime.timezone.utc)
        blobs = [
            _FakeBlob(
                'policies/a.txt',
                etag='"etag-a"',
                last_modified=last_modified,
                size=10,
                content_type='text/plain',
            )
        ]
        source = AzureBlobSource(container='company-docs', client=_FakeContainerClient(blobs=blobs))

        [document] = list(source.list_documents())

        self.assertEqual(document.document_id, 'azure-blob://myaccount/company-docs/policies/a.txt')
        self.assertEqual(document.uri, document.document_id)
        self.assertEqual(document.name, 'policies/a.txt')
        self.assertEqual(document.metadata.etag, 'etag-a')
        self.assertEqual(document.metadata.content_length, 10)
        self.assertEqual(document.metadata.content_type, 'text/plain')
        self.assertEqual(document.metadata.last_modified, last_modified.isoformat())

    def test_skips_soft_deleted_blobs(self):
        blobs = [_FakeBlob('a.txt', deleted=True), _FakeBlob('b.txt', deleted=False)]
        source = AzureBlobSource(container='docs', client=_FakeContainerClient(blobs=blobs))
        documents = list(source.list_documents())
        self.assertEqual([d.name for d in documents], ['b.txt'])

    def test_prefix_is_forwarded_to_list_blobs(self):
        container_client = _FakeContainerClient()
        source = AzureBlobSource(container='docs', prefix='configured/', client=container_client)
        list(source.list_documents())
        self.assertEqual(container_client.list_calls[0]['name_starts_with'], 'configured/')

    def test_call_level_prefix_overrides_the_configured_one(self):
        container_client = _FakeContainerClient()
        source = AzureBlobSource(container='docs', prefix='configured/', client=container_client)
        list(source.list_documents(prefix='override/'))
        self.assertEqual(container_client.list_calls[0]['name_starts_with'], 'override/')


class AzureBlobSourceGetDocumentTest(unittest.TestCase):
    def test_returns_blob_bytes(self):
        source = AzureBlobSource(
            container='docs', client=_FakeContainerClient(downloads={'a.txt': b'hello world'})
        )
        content = source.get_document('azure-blob://myaccount/docs/a.txt')
        self.assertEqual(content, b'hello world')

    def test_document_id_from_a_different_container_is_not_found(self):
        source = AzureBlobSource(container='docs', client=_FakeContainerClient())
        with self.assertRaises(SourceNotFoundError):
            source.get_document('azure-blob://myaccount/other-container/a.txt')


class AzureBlobSourceGetMetadataTest(unittest.TestCase):
    def test_returns_normalized_metadata(self):
        last_modified = datetime.datetime(2026, 9, 1, tzinfo=datetime.timezone.utc)
        properties = _FakeBlob(
            'a.txt',
            etag='"etag-1"',
            last_modified=last_modified,
            size=42,
            content_type='text/plain',
        )
        source = AzureBlobSource(
            container='docs', client=_FakeContainerClient(properties={'a.txt': properties})
        )
        metadata = source.get_metadata('azure-blob://myaccount/docs/a.txt')
        self.assertEqual(metadata.etag, 'etag-1')
        self.assertEqual(metadata.content_length, 42)
        self.assertEqual(metadata.content_type, 'text/plain')


class AzureBlobSourceErrorClassificationTest(unittest.TestCase):
    def test_resource_not_found_error_is_source_not_found(self):
        source = AzureBlobSource(
            container='docs',
            client=_FakeContainerClient(exception=_fake_error('ResourceNotFoundError')),
        )
        with self.assertRaises(SourceNotFoundError):
            source.get_document('azure-blob://myaccount/docs/a.txt')

    def test_client_authentication_error_is_non_retryable(self):
        source = AzureBlobSource(
            container='docs',
            client=_FakeContainerClient(exception=_fake_error('ClientAuthenticationError')),
        )
        with self.assertRaises(SourceAccessDeniedError):
            source.get_document('azure-blob://myaccount/docs/a.txt')

    def test_service_request_error_is_transient(self):
        source = AzureBlobSource(
            container='docs',
            client=_FakeContainerClient(exception=_fake_error('ServiceRequestError')),
        )
        with self.assertRaises(TransientSourceError):
            source.get_document('azure-blob://myaccount/docs/a.txt')

    def test_unrecognized_error_with_5xx_status_is_transient(self):
        source = AzureBlobSource(
            container='docs',
            client=_FakeContainerClient(exception=_fake_error('SomeFutureError', status_code=503)),
        )
        with self.assertRaises(TransientSourceError):
            source.get_document('azure-blob://myaccount/docs/a.txt')

    def test_unrecognized_error_with_403_status_is_non_retryable(self):
        source = AzureBlobSource(
            container='docs',
            client=_FakeContainerClient(exception=_fake_error('SomeFutureError', status_code=403)),
        )
        with self.assertRaises(SourceAccessDeniedError):
            source.get_document('azure-blob://myaccount/docs/a.txt')


if __name__ == '__main__':
    unittest.main()
