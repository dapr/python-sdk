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

from __future__ import annotations

from typing import Any, Iterator, Optional

from dapr.ext.rag.errors import (
    OptionalDependencyError,
    RagError,
    SourceAccessDeniedError,
    SourceNotFoundError,
    TransientSourceError,
)
from dapr.ext.rag.models import SourceDocument, SourceMetadata, SourceProvider
from dapr.ext.rag.sources.base import DocumentSource

# See dapr/ext/rag/AGENTS.md for why the optional-dependency guard lives here,
# per adapter module, rather than once in dapr/ext/rag/__init__.py.
try:
    from azure.storage.blob import BlobServiceClient
except ImportError:  # pragma: no cover - exercised only without azure-storage-blob installed
    BlobServiceClient = None  # type: ignore[assignment,misc]

try:
    from azure.identity import DefaultAzureCredential
except ImportError:  # pragma: no cover - exercised only without azure-identity installed
    DefaultAzureCredential = None  # type: ignore[assignment,misc]

# Classified (and caught, in list_documents/get_document/get_metadata below)
# by exception *name* rather than `isinstance` against the real azure-core
# classes: that works identically whether azure-core is installed at all, and
# whether the caller injected a real client or a test's look-alike fake that
# isn't actually a subclass of those classes.
_NOT_FOUND_EXCEPTION_NAMES = frozenset({'ResourceNotFoundError'})
_ACCESS_DENIED_EXCEPTION_NAMES = frozenset({'ClientAuthenticationError'})
_TRANSIENT_EXCEPTION_NAMES = frozenset({'ServiceRequestError', 'ServiceResponseError'})


class AzureBlobSource(DocumentSource):
    """Reads documents from an Azure Blob Storage container.

    `DefaultAzureCredential` (managed identity, workload identity, Azure CLI
    login, ...) is the preferred authentication mechanism and requires no
    secrets in configuration. A `connection_string` is accepted for local
    development and testing (e.g. against Azurite), and an explicit
    `credential` may be injected for any other `azure-identity` credential
    type.
    """

    def __init__(
        self,
        *,
        account_url: Optional[str] = None,
        container: str,
        prefix: Optional[str] = None,
        credential: Optional[Any] = None,
        connection_string: Optional[str] = None,
        page_size: int = 1000,
        client: Optional[Any] = None,
    ) -> None:
        """Initializes an AzureBlobSource.

        Args:
            account_url: The storage account's blob endpoint, e.g.
                `https://example.blob.core.windows.net`. Required unless
                `connection_string` or `client` is given.
            container: The container to read from.
            prefix: Restricts `list_documents()` to blobs under this prefix
                when the call doesn't override it.
            credential: An `azure-identity` credential. Defaults to
                `DefaultAzureCredential()` when neither this nor
                `connection_string` is given.
            connection_string: A full connection string (e.g. Azurite's
                well-known development string, or an account connection
                string) -- an alternative to `account_url` + `credential`
                for local development and testing.
            page_size: Blobs requested per listing page.
            client: A pre-built `BlobServiceClient` or `ContainerClient` to
                use instead of constructing one -- bypasses the
                `azure-storage-blob`/`azure-identity` dependency check
                entirely, which is how tests exercise this class without
                those packages installed.

        Raises:
            OptionalDependencyError: `azure-storage-blob` (or
                `azure-identity`, when a credential must be constructed) is
                not installed and no `client` was given.
            ValueError: Neither `client`, `connection_string`, nor
                `account_url` was given.
        """
        self._container_name = container
        self._prefix = prefix
        self._page_size = page_size

        if client is not None:
            self._container_client = self._as_container_client(client, container)
        else:
            self._container_client = self._build_container_client(
                account_url=account_url,
                container=container,
                credential=credential,
                connection_string=connection_string,
            )
        self._account_name = getattr(self._container_client, 'account_name', None) or 'unknown'

    @staticmethod
    def _as_container_client(client: Any, container: str) -> Any:
        get_container_client = getattr(client, 'get_container_client', None)
        if callable(get_container_client):
            return get_container_client(container)  # a BlobServiceClient was injected
        return client  # a ContainerClient was injected directly

    @staticmethod
    def _build_container_client(
        *,
        account_url: Optional[str],
        container: str,
        credential: Optional[Any],
        connection_string: Optional[str],
    ) -> Any:
        if BlobServiceClient is None:
            raise OptionalDependencyError(
                package='azure-storage-blob', extra='rag-azure', feature='AzureBlobSource'
            )
        if connection_string is not None:
            service_client = BlobServiceClient.from_connection_string(connection_string)
            return service_client.get_container_client(container)
        if account_url is None:
            raise ValueError('AzureBlobSource requires account_url, connection_string, or client.')
        if credential is None:
            if DefaultAzureCredential is None:
                raise OptionalDependencyError(
                    package='azure-identity', extra='rag-azure', feature='AzureBlobSource'
                )
            credential = DefaultAzureCredential()
        service_client = BlobServiceClient(account_url=account_url, credential=credential)
        return service_client.get_container_client(container)

    @property
    def provider(self) -> SourceProvider:
        return SourceProvider.AZURE_BLOB

    def list_documents(self, prefix: Optional[str] = None) -> Iterator[SourceDocument]:
        effective_prefix = prefix if prefix is not None else self._prefix
        try:
            blobs = self._container_client.list_blobs(
                name_starts_with=effective_prefix or None,
                results_per_page=self._page_size,
            )
            for blob in blobs:
                if getattr(blob, 'deleted', False):
                    continue
                yield self._to_source_document(blob)
        except Exception as exc:
            raise self._classify(exc) from exc

    def get_document(self, document_id: str) -> bytes:
        blob_name = self._blob_name_from_document_id(document_id)
        try:
            downloader = self._container_client.download_blob(blob_name)
            return downloader.readall()
        except Exception as exc:
            raise self._classify(exc) from exc

    def get_metadata(self, document_id: str) -> SourceMetadata:
        blob_name = self._blob_name_from_document_id(document_id)
        try:
            properties = self._container_client.get_blob_client(blob_name).get_blob_properties()
        except Exception as exc:
            raise self._classify(exc) from exc
        return self._to_metadata(properties)

    def close(self) -> None:
        close = getattr(self._container_client, 'close', None)
        if callable(close):
            close()

    def _to_source_document(self, blob: Any) -> SourceDocument:
        document_id = self._document_id(blob.name)
        return SourceDocument(
            document_id=document_id,
            provider=SourceProvider.AZURE_BLOB,
            uri=document_id,
            name=blob.name,
            metadata=self._to_metadata(blob),
        )

    @staticmethod
    def _to_metadata(blob_like: Any) -> SourceMetadata:
        content_settings = getattr(blob_like, 'content_settings', None)
        last_modified = getattr(blob_like, 'last_modified', None)
        return SourceMetadata(
            etag=_normalize_etag(getattr(blob_like, 'etag', None)),
            version_id=getattr(blob_like, 'version_id', None),
            last_modified=last_modified.isoformat() if last_modified is not None else None,
            content_length=getattr(blob_like, 'size', None),
            content_type=getattr(content_settings, 'content_type', None),
        )

    def _document_id(self, blob_name: str) -> str:
        return f'azure-blob://{self._account_name}/{self._container_name}/{blob_name}'

    def _blob_name_from_document_id(self, document_id: str) -> str:
        prefix = f'azure-blob://{self._account_name}/{self._container_name}/'
        if not document_id.startswith(prefix):
            raise SourceNotFoundError(
                f'{document_id!r} does not belong to container {self._container_name!r}'
            )
        return document_id[len(prefix) :]

    @staticmethod
    def _classify(exc: Exception) -> RagError:
        name = type(exc).__name__
        if name in _NOT_FOUND_EXCEPTION_NAMES:
            return SourceNotFoundError(str(exc))
        if name in _ACCESS_DENIED_EXCEPTION_NAMES:
            return SourceAccessDeniedError(str(exc))
        if name in _TRANSIENT_EXCEPTION_NAMES:
            return TransientSourceError(str(exc))  # network-level failure, always transient

        status = getattr(exc, 'status_code', None)
        if status == 403:
            return SourceAccessDeniedError(str(exc))
        if status == 429 or (isinstance(status, int) and status >= 500):
            return TransientSourceError(str(exc))
        if isinstance(status, int) and 400 <= status < 500:
            return SourceAccessDeniedError(str(exc))
        return TransientSourceError(str(exc))


def _normalize_etag(raw_etag: Optional[str]) -> Optional[str]:
    return raw_etag.strip('"') if raw_etag else None
