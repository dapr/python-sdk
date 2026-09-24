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

# Normalizes cloud storage event notifications into a small, provider-agnostic
# shape (`SourceChangeEvent`). Deliberately separate from `pipeline.py`:
# parsing an S3 Event Notification or an Azure Event Grid envelope (delivered
# through Service Bus, or directly through a Dapr pub/sub component) is
# provider-specific plumbing that has nothing to do with durable ingestion,
# and keeping it here means `DurableRAGPipeline` never needs to know these
# payload shapes exist. See `examples/rag/pubsub_trigger.py` (S3/EventBridge)
# and `examples/rag/pubsub_trigger_servicebus.py` (Azure) for runnable Dapr
# pub/sub subscribers built on these functions, and `EventDeduplicator` below
# for handling at-least-once/duplicate delivery.

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Optional
from urllib.parse import unquote_plus

from dapr.clients import DaprClient
from dapr.ext.rag.fingerprints import compute_content_hash
from dapr.ext.rag.models import SourceChangeEvent, SourceProvider


@dataclass(frozen=True, slots=True)
class StorageEventNotification:
    """A normalized "something changed at this object/blob" event.

    An intermediate shape: still close to the provider's own vocabulary
    (`event_type` is the raw event name), before `to_source_change_event`
    maps it onto the fully provider-neutral `SourceChangeEvent`.
    """

    provider: str  # SourceProvider value
    event_type: str  # provider-native event name, e.g. 'ObjectCreated:Put'
    bucket_or_container: str
    key_or_blob_name: str
    event_id: str
    etag: Optional[str]
    version_id: Optional[str]
    occurred_at: Optional[str]
    raw: dict[str, Any]


def parse_s3_event_notifications(payload: dict[str, Any]) -> list[StorageEventNotification]:
    """Parses an S3 Event Notification payload into `StorageEventNotification`s.

    Handles the standard S3 Event Notification JSON shape (`{"Records": [...]}`)
    as delivered via SNS, SQS, or EventBridge and forwarded to a Dapr
    subscriber through a pub/sub component -- one payload commonly batches
    multiple records.

    Args:
        payload: The decoded event body.

    Returns:
        One `StorageEventNotification` per record (empty if `payload` has no
        `Records`, e.g. an unrelated or malformed message).
    """
    notifications = []
    for record in payload.get('Records', []):
        bucket = record.get('s3', {}).get('bucket', {}).get('name', '')
        s3_object = record.get('s3', {}).get('object', {})
        raw_key = s3_object.get('key', '')
        event_name = record.get('eventName', '')
        # S3 notifications have no top-level event ID; `sequencer` is a
        # real per-object-version identifier when present, so it's a stable
        # idempotency key -- fall back to hashing the identifying fields.
        sequencer = s3_object.get('sequencer')
        event_id = sequencer or compute_content_hash(
            f'{bucket}:{raw_key}:{event_name}:{s3_object.get("eTag", "")}'.encode()
        )
        notifications.append(
            StorageEventNotification(
                provider=SourceProvider.S3.value,
                event_type=event_name,
                bucket_or_container=bucket,
                key_or_blob_name=unquote_plus(raw_key),
                event_id=event_id,
                etag=_strip_quotes(s3_object.get('eTag')),
                version_id=s3_object.get('versionId'),
                occurred_at=record.get('eventTime'),
                raw=record,
            )
        )
    return notifications


_AZURE_BLOB_SUBJECT = re.compile(r'/containers/(?P<container>[^/]+)/blobs/(?P<blob_name>.+)$')


def parse_azure_blob_event(payload: dict[str, Any]) -> Optional[StorageEventNotification]:
    """Parses one Azure Event Grid blob-storage event into a `StorageEventNotification`.

    Handles `Microsoft.Storage.BlobCreated` / `BlobDeleted` events (and any
    other Storage event carrying the same `subject` shape), in either Event
    Grid schema (`eventType`/`eventTime`/`id`) or CloudEvents schema
    (`type`/`time`/`id`) -- both are delivered with the same field meanings
    under different names. Works whether the event arrives directly through
    a Dapr pub/sub component or was relayed through Azure Service Bus first
    (unwrap the Service Bus message body before calling this). Event Grid
    may deliver a batch as a JSON array; call this once per element.

    Args:
        payload: One decoded Event Grid/CloudEvents event.

    Returns:
        A `StorageEventNotification`, or `None` if `payload["subject"]`
        doesn't match the expected `.../containers/{c}/blobs/{b}` shape.
    """
    match = _AZURE_BLOB_SUBJECT.search(payload.get('subject', ''))
    if not match:
        return None
    data = payload.get('data', {})
    return StorageEventNotification(
        provider=SourceProvider.AZURE_BLOB.value,
        event_type=payload.get('eventType') or payload.get('type', ''),
        bucket_or_container=match.group('container'),
        key_or_blob_name=match.group('blob_name'),
        event_id=payload.get('id', ''),
        etag=_strip_quotes(data.get('etag')),
        version_id=data.get('versionId') or data.get('snapshot'),
        occurred_at=payload.get('eventTime') or payload.get('time'),
        raw=payload,
    )


_DELETED_EVENT_NAMES = frozenset({'Microsoft.Storage.BlobDeleted'})


def to_source_change_event(notification: StorageEventNotification) -> SourceChangeEvent:
    """Maps a provider-flavored `StorageEventNotification` onto a `SourceChangeEvent`.

    `event_type` is normalized to `'created'` / `'deleted'` (neither S3 nor
    Azure Blob notifications distinguish a fresh upload from an overwrite at
    the event-name level -- both are `'created'`; the pipeline's own
    ETag-based document-changed detection, not the event stream, is the
    authority on whether content actually changed).
    """
    if notification.provider == SourceProvider.S3.value:
        event_type = 'deleted' if notification.event_type.startswith('ObjectRemoved') else 'created'
        source_document_id = (
            f's3://{notification.bucket_or_container}/{notification.key_or_blob_name}'
        )
    else:
        event_type = 'deleted' if notification.event_type in _DELETED_EVENT_NAMES else 'created'
        source_document_id = (
            f'azure-blob://{notification.bucket_or_container}/{notification.key_or_blob_name}'
        )

    return SourceChangeEvent(
        provider=notification.provider,
        event_type=event_type,
        source_document_id=source_document_id,
        uri=source_document_id,
        etag=notification.etag,
        version_id=notification.version_id,
        occurred_at=notification.occurred_at,
        event_id=notification.event_id,
    )


class EventDeduplicator:
    """Tracks handled event IDs in Dapr state to absorb duplicate deliveries.

    Service Bus, SQS, and Event Grid all offer only at-least-once delivery,
    and a consumer restart can also cause redelivery. Checking (and
    recording) `event.event_id` here before acting on an event keeps a
    duplicate from starting a second, redundant ingestion run.
    """

    def __init__(
        self,
        *,
        state_store_name: str,
        dapr_client: Optional[DaprClient] = None,
        ttl_seconds: int = 86400,
    ) -> None:
        """Initializes an EventDeduplicator.

        Args:
            state_store_name: The Dapr state store to record seen event IDs in.
            dapr_client: A `DaprClient` to reuse; a new one is created (and
                owned/closed by this instance) when omitted.
            ttl_seconds: How long a seen-event marker is kept. Only needs to
                cover the provider's own redelivery/retry window, not forever.
        """
        self._state_store_name = state_store_name
        self._owns_client = dapr_client is None
        self._client = dapr_client or DaprClient()
        self._ttl_seconds = ttl_seconds

    def already_seen(self, event_id: str) -> bool:
        """Returns whether `event_id` was already marked seen."""
        response = self._client.get_state(
            store_name=self._state_store_name, key=self._key(event_id)
        )
        return bool(response.data)

    def mark_seen(self, event_id: str) -> None:
        """Records `event_id` as handled, for `ttl_seconds`."""
        self._client.save_state(
            store_name=self._state_store_name,
            key=self._key(event_id),
            value='1',
            state_metadata={'ttlInSeconds': str(self._ttl_seconds)},
        )

    def close(self) -> None:
        """Releases the underlying `DaprClient`, if this instance created it."""
        if self._owns_client:
            self._client.close()

    @staticmethod
    def _key(event_id: str) -> str:
        return f'rag:seen-event:{event_id}'


def _strip_quotes(value: Optional[str]) -> Optional[str]:
    return value.strip('"') if value else value
