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

# Guarded like every other optional adapter in this package (see
# dapr/ext/rag/AGENTS.md): the import is attempted once at module load, and a
# missing package only becomes an error when S3Source is actually
# instantiated without an injected client -- never at `import dapr.ext.rag`.
try:
    import boto3
    from botocore.exceptions import BotoCoreError, ClientError
except ImportError:  # pragma: no cover - exercised only without boto3 installed
    boto3 = None  # type: ignore[assignment]
    BotoCoreError = ClientError = Exception  # type: ignore[assignment,misc]

_THROTTLE_CODES = frozenset(
    {
        'SlowDown',
        'RequestTimeout',
        'RequestTimeTooSkewed',
        'ThrottlingException',
        'ServiceUnavailable',
        'InternalError',
        'Throttling',
    }
)
_NOT_FOUND_CODES = frozenset({'NoSuchKey', 'NoSuchBucket', '404'})
_ACCESS_DENIED_CODES = frozenset({'AccessDenied', 'InvalidAccessKeyId', 'SignatureDoesNotMatch'})


class S3Source(DocumentSource):
    """Reads documents from an Amazon S3 (or S3-compatible) bucket.

    Credentials are resolved via boto3's standard credential-provider chain
    (environment, shared config/credentials files, IAM instance/task role,
    SSO, ...) by default -- nothing here requires static credentials in
    configuration. Explicit `aws_access_key_id`/`aws_secret_access_key` are
    accepted only for cases like local testing against LocalStack.
    """

    def __init__(
        self,
        *,
        bucket: str,
        prefix: Optional[str] = None,
        region_name: Optional[str] = None,
        endpoint_url: Optional[str] = None,
        aws_access_key_id: Optional[str] = None,
        aws_secret_access_key: Optional[str] = None,
        aws_session_token: Optional[str] = None,
        page_size: int = 1000,
        client: Optional[Any] = None,
    ) -> None:
        """Initializes an S3Source.

        Args:
            bucket: The S3 bucket to read from.
            prefix: Restricts `list_documents()` to keys under this prefix
                when the call doesn't override it.
            region_name: Optional AWS region; otherwise resolved by boto3.
            endpoint_url: Optional endpoint override, e.g.
                `http://localhost:4566` for LocalStack or any S3-compatible
                store. Ignored if `client` is given.
            aws_access_key_id: Optional static credential. Prefer the default
                credential chain; this exists for local/test setups (e.g.
                LocalStack's fixed test credentials).
            aws_secret_access_key: Paired with `aws_access_key_id`.
            aws_session_token: Optional session token for temporary credentials.
            page_size: Objects requested per `ListObjectsV2` page.
            client: A pre-built boto3 S3 client to use instead of
                constructing one -- bypasses the `boto3` dependency check
                entirely, which is how tests exercise this class without
                boto3 installed.

        Raises:
            OptionalDependencyError: `boto3` is not installed and no `client`
                was given.
        """
        self._bucket = bucket
        self._prefix = prefix
        self._page_size = page_size

        if client is not None:
            self._client = client
        else:
            if boto3 is None:
                raise OptionalDependencyError(package='boto3', extra='rag-s3', feature='S3Source')
            session_kwargs: dict[str, Any] = {}
            if region_name is not None:
                session_kwargs['region_name'] = region_name
            if aws_access_key_id is not None:
                session_kwargs['aws_access_key_id'] = aws_access_key_id
            if aws_secret_access_key is not None:
                session_kwargs['aws_secret_access_key'] = aws_secret_access_key
            if aws_session_token is not None:
                session_kwargs['aws_session_token'] = aws_session_token
            self._client = boto3.client('s3', endpoint_url=endpoint_url, **session_kwargs)

    @property
    def provider(self) -> SourceProvider:
        return SourceProvider.S3

    def list_documents(self, prefix: Optional[str] = None) -> Iterator[SourceDocument]:
        effective_prefix = prefix if prefix is not None else self._prefix
        list_kwargs: dict[str, Any] = {'Bucket': self._bucket}
        if effective_prefix:
            list_kwargs['Prefix'] = effective_prefix

        try:
            paginator = self._client.get_paginator('list_objects_v2')
            for page in paginator.paginate(
                PaginationConfig={'PageSize': self._page_size}, **list_kwargs
            ):
                for obj in page.get('Contents', []):
                    key = obj['Key']
                    if key.endswith('/') and obj.get('Size', 0) == 0:
                        continue  # "directory marker" placeholder object, not a document
                    yield self._to_source_document(key, obj)
        except (ClientError, BotoCoreError) as exc:
            raise self._classify(exc) from exc

    def get_document(self, document_id: str) -> bytes:
        key = self._key_from_document_id(document_id)
        try:
            response = self._client.get_object(Bucket=self._bucket, Key=key)
            return response['Body'].read()
        except (ClientError, BotoCoreError) as exc:
            raise self._classify(exc) from exc

    def get_metadata(self, document_id: str) -> SourceMetadata:
        key = self._key_from_document_id(document_id)
        try:
            response = self._client.head_object(Bucket=self._bucket, Key=key)
        except (ClientError, BotoCoreError) as exc:
            raise self._classify(exc) from exc
        return SourceMetadata(
            etag=_strip_etag(response.get('ETag')),
            version_id=response.get('VersionId'),
            last_modified=_isoformat(response.get('LastModified')),
            content_length=response.get('ContentLength'),
            content_type=response.get('ContentType'),
        )

    def close(self) -> None:
        close = getattr(self._client, 'close', None)
        if callable(close):
            close()

    def _to_source_document(self, key: str, listing_entry: dict[str, Any]) -> SourceDocument:
        document_id = self._document_id(key)
        return SourceDocument(
            document_id=document_id,
            provider=SourceProvider.S3,
            uri=document_id,
            name=key,
            metadata=SourceMetadata(
                etag=_strip_etag(listing_entry.get('ETag')),
                version_id=None,  # ListObjectsV2 doesn't return VersionId; head_object does.
                last_modified=_isoformat(listing_entry.get('LastModified')),
                content_length=listing_entry.get('Size'),
                content_type=None,
            ),
        )

    def _document_id(self, key: str) -> str:
        return f's3://{self._bucket}/{key}'

    def _key_from_document_id(self, document_id: str) -> str:
        prefix = f's3://{self._bucket}/'
        if not document_id.startswith(prefix):
            raise SourceNotFoundError(f'{document_id!r} does not belong to bucket {self._bucket!r}')
        return document_id[len(prefix) :]

    @staticmethod
    def _classify(exc: Exception) -> RagError:
        if not isinstance(exc, ClientError):
            # A BotoCoreError that isn't a ClientError (e.g. EndpointConnectionError,
            # ConnectTimeoutError) is a network-level failure -- always transient.
            return TransientSourceError(str(exc))

        error = exc.response.get('Error', {}) if hasattr(exc, 'response') else {}
        code = error.get('Code', '')
        status = exc.response.get('ResponseMetadata', {}).get('HTTPStatusCode')

        if code in _NOT_FOUND_CODES:
            return SourceNotFoundError(str(exc))
        if code in _ACCESS_DENIED_CODES or status == 403:
            return SourceAccessDeniedError(str(exc))
        if code in _THROTTLE_CODES or (isinstance(status, int) and status >= 500):
            return TransientSourceError(str(exc))
        # Unrecognized 4xx: most likely a request/config problem retrying won't fix.
        if isinstance(status, int) and 400 <= status < 500:
            return SourceAccessDeniedError(str(exc))
        return TransientSourceError(str(exc))


def _strip_etag(raw_etag: Optional[str]) -> Optional[str]:
    return raw_etag.strip('"') if raw_etag else None


def _isoformat(value: Any) -> Optional[str]:
    isoformat = getattr(value, 'isoformat', None)
    return isoformat() if callable(isoformat) else None
