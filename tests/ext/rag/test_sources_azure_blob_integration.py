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

# Real, opt-in test of AzureBlobSource against a live Azurite container -- not mocks. Unlike
# test_sources_azure_blob.py (which exercises the class's logic against hand-written fakes, so
# it needs neither azure-storage-blob nor a running emulator), this proves the exception-name
# based classification in _classify actually matches what a *real* azure-storage-blob client
# raises against a *real* (if emulated) service -- something a fake, by construction, can't.
#
# Marked e2e (excluded from the default `-m "not e2e"` suite; see root AGENTS.md) and skips
# itself cleanly if Azurite isn't reachable, rather than failing.
#
# Prerequisite (start once, independent of any single test run):
#
#   docker run -d --rm --name rag-it-azurite -p 10000:10000 \
#       mcr.microsoft.com/azure-storage/azurite:latest azurite-blob --blobHost 0.0.0.0 --blobPort 10000
#
# Then:
#
#   uv run pytest tests/ext/rag/test_sources_azure_blob_integration.py -m e2e -v
#
# Override RAG_IT_AZURITE_CONNECTION_STRING if Azurite isn't at the default address. Uses
# Azurite's well-known, publicly-documented development account key (not a secret) unless
# overridden. Each test run uses a fresh, randomly-suffixed container name and deletes it
# afterward -- the Azurite container itself is not managed by this file, matching how
# test_pipeline_integration.py treats LocalStack/pgvector.

from __future__ import annotations

import os
import uuid

import pytest

from dapr.ext.rag.errors import SourceNotFoundError
from dapr.ext.rag.models import SourceProvider
from dapr.ext.rag.sources.azure_blob import AzureBlobSource

pytestmark = pytest.mark.e2e

_AZURITE_WELL_KNOWN_CONNECTION_STRING = (
    'DefaultEndpointsProtocol=http;AccountName=devstoreaccount1;AccountKey=Eby8vdM02xNOcqFlqUwJPLlm'
    'EtlCDXJ1OUzFT50uSRZ6IFsuFq2UVErCz4I6tq/K1SZFPTOtr/KBHBeksoGMGw==;BlobEndpoint=http://127.0.0.1:'
    '10000/devstoreaccount1;'
)
CONNECTION_STRING = os.environ.get(
    'RAG_IT_AZURITE_CONNECTION_STRING', _AZURITE_WELL_KNOWN_CONNECTION_STRING
)


@pytest.fixture(scope='module')
def blob_service_client():
    """A `BlobServiceClient` against Azurite, or a clean `pytest.skip` if unreachable."""
    try:
        from azure.storage.blob import BlobServiceClient
    except ImportError:
        pytest.skip('azure-storage-blob is not installed')

    client = BlobServiceClient.from_connection_string(CONNECTION_STRING)
    try:
        next(client.list_containers(results_per_page=1).by_page(), None)
    except Exception as exc:
        pytest.skip(
            f'Azurite not reachable via {CONNECTION_STRING!r} ({exc}) -- see module docstring'
        )

    yield client
    client.close()


@pytest.fixture()
def container(blob_service_client):
    name = f'rag-it-{uuid.uuid4().hex[:12]}'
    blob_service_client.create_container(name)
    yield name
    blob_service_client.delete_container(name)


@pytest.fixture()
def source(container):
    src = AzureBlobSource(connection_string=CONNECTION_STRING, container=container)
    yield src
    src.close()


def test_lists_and_downloads_a_real_blob_with_etag_and_metadata(
    blob_service_client, container, source
):
    container_client = blob_service_client.get_container_client(container)
    container_client.upload_blob(
        'policies/remote-work.txt',
        b'Employees may work remotely three days per week.',
        content_settings=_content_settings('text/plain'),
    )

    [document] = list(source.list_documents())

    assert document.provider == SourceProvider.AZURE_BLOB
    assert document.name == 'policies/remote-work.txt'
    assert document.metadata.etag  # Azurite assigns a real ETag; must not be empty/None
    assert document.metadata.content_type == 'text/plain'
    assert document.metadata.content_length == len(
        b'Employees may work remotely three days per week.'
    )

    content = source.get_document(document.document_id)
    assert content == b'Employees may work remotely three days per week.'

    metadata = source.get_metadata(document.document_id)
    assert metadata.etag == document.metadata.etag


def test_get_document_raises_not_found_for_a_real_missing_blob(container, source):
    missing_id = f'azure-blob://devstoreaccount1/{container}/does-not-exist.txt'
    with pytest.raises(SourceNotFoundError):
        source.get_document(missing_id)


def test_prefix_restricts_listing_to_matching_blobs(blob_service_client, container, source):
    container_client = blob_service_client.get_container_client(container)
    container_client.upload_blob('policies/a.txt', b'a')
    container_client.upload_blob('other/b.txt', b'b')

    documents = list(source.list_documents(prefix='policies/'))

    assert [d.name for d in documents] == ['policies/a.txt']


def _content_settings(content_type: str):
    from azure.storage.blob import ContentSettings

    return ContentSettings(content_type=content_type)
