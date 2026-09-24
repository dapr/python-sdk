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

from dapr.ext.rag.triggers import (
    EventDeduplicator,
    parse_azure_blob_event,
    parse_s3_event_notifications,
    to_source_change_event,
)


class ParseS3EventNotificationsTest(unittest.TestCase):
    def test_parses_a_single_record(self):
        payload = {
            'Records': [
                {
                    'eventName': 'ObjectCreated:Put',
                    's3': {'bucket': {'name': 'company-docs'}, 'object': {'key': 'policies/a.txt'}},
                }
            ]
        }
        [event] = parse_s3_event_notifications(payload)
        self.assertEqual(event.provider, 's3')
        self.assertEqual(event.event_type, 'ObjectCreated:Put')
        self.assertEqual(event.bucket_or_container, 'company-docs')
        self.assertEqual(event.key_or_blob_name, 'policies/a.txt')

    def test_parses_multiple_batched_records(self):
        payload = {
            'Records': [
                {
                    'eventName': 'ObjectCreated:Put',
                    's3': {'bucket': {'name': 'b'}, 'object': {'key': 'a.txt'}},
                },
                {
                    'eventName': 'ObjectRemoved:Delete',
                    's3': {'bucket': {'name': 'b'}, 'object': {'key': 'b.txt'}},
                },
            ]
        }
        events = parse_s3_event_notifications(payload)
        self.assertEqual(
            [e.event_type for e in events], ['ObjectCreated:Put', 'ObjectRemoved:Delete']
        )

    def test_url_decodes_the_object_key(self):
        payload = {
            'Records': [
                {
                    'eventName': 'ObjectCreated:Put',
                    's3': {'bucket': {'name': 'b'}, 'object': {'key': 'a+b%3D1.txt'}},
                }
            ]
        }
        [event] = parse_s3_event_notifications(payload)
        self.assertEqual(event.key_or_blob_name, 'a b=1.txt')

    def test_unrelated_payload_yields_no_events(self):
        self.assertEqual(parse_s3_event_notifications({'not': 'an s3 event'}), [])

    def test_derives_a_stable_event_id_from_the_sequencer(self):
        payload = {
            'Records': [
                {
                    'eventName': 'ObjectCreated:Put',
                    's3': {
                        'bucket': {'name': 'b'},
                        'object': {'key': 'a.txt', 'sequencer': '0055AED6DCD90281E5'},
                    },
                }
            ]
        }
        [event] = parse_s3_event_notifications(payload)
        self.assertEqual(event.event_id, '0055AED6DCD90281E5')

    def test_derives_a_deterministic_event_id_without_a_sequencer(self):
        payload = {
            'Records': [
                {
                    'eventName': 'ObjectCreated:Put',
                    's3': {'bucket': {'name': 'b'}, 'object': {'key': 'a.txt'}},
                }
            ]
        }
        first = parse_s3_event_notifications(payload)[0].event_id
        second = parse_s3_event_notifications(payload)[0].event_id
        self.assertEqual(first, second)
        self.assertTrue(first)

    def test_captures_etag_and_version_id(self):
        payload = {
            'Records': [
                {
                    'eventName': 'ObjectCreated:Put',
                    's3': {
                        'bucket': {'name': 'b'},
                        'object': {'key': 'a.txt', 'eTag': '"abc123"', 'versionId': 'v1'},
                    },
                }
            ]
        }
        [event] = parse_s3_event_notifications(payload)
        self.assertEqual(event.etag, 'abc123')
        self.assertEqual(event.version_id, 'v1')


class ParseAzureBlobEventTest(unittest.TestCase):
    def test_parses_a_blob_created_event(self):
        payload = {
            'eventType': 'Microsoft.Storage.BlobCreated',
            'subject': '/blobServices/default/containers/company-docs/blobs/policies/a.txt',
        }
        event = parse_azure_blob_event(payload)
        self.assertEqual(event.provider, 'azure-blob')
        self.assertEqual(event.event_type, 'Microsoft.Storage.BlobCreated')
        self.assertEqual(event.bucket_or_container, 'company-docs')
        self.assertEqual(event.key_or_blob_name, 'policies/a.txt')

    def test_returns_none_for_a_subject_without_a_blob_path(self):
        payload = {'eventType': 'Microsoft.Storage.BlobCreated', 'subject': '/blobServices/default'}
        self.assertIsNone(parse_azure_blob_event(payload))

    def test_returns_none_for_a_missing_subject(self):
        self.assertIsNone(parse_azure_blob_event({'eventType': 'Microsoft.Storage.BlobCreated'}))

    def test_accepts_cloudevents_schema_field_names(self):
        payload = {
            'id': 'event-1',
            'type': 'Microsoft.Storage.BlobCreated',
            'time': '2026-09-10T00:00:00Z',
            'subject': '/blobServices/default/containers/company-docs/blobs/a.txt',
            'data': {'etag': '"abc123"'},
        }
        event = parse_azure_blob_event(payload)
        self.assertEqual(event.event_type, 'Microsoft.Storage.BlobCreated')
        self.assertEqual(event.event_id, 'event-1')
        self.assertEqual(event.occurred_at, '2026-09-10T00:00:00Z')
        self.assertEqual(event.etag, 'abc123')

    def test_captures_event_grid_schema_id_and_etag(self):
        payload = {
            'id': 'event-2',
            'eventType': 'Microsoft.Storage.BlobCreated',
            'eventTime': '2026-09-10T00:00:00Z',
            'subject': '/blobServices/default/containers/company-docs/blobs/a.txt',
            'data': {'etag': '"xyz789"'},
        }
        event = parse_azure_blob_event(payload)
        self.assertEqual(event.event_id, 'event-2')
        self.assertEqual(event.etag, 'xyz789')


class ToSourceChangeEventTest(unittest.TestCase):
    def test_s3_object_created_normalizes_to_created(self):
        [notification] = parse_s3_event_notifications(
            {
                'Records': [
                    {
                        'eventName': 'ObjectCreated:Put',
                        's3': {'bucket': {'name': 'b'}, 'object': {'key': 'a.txt'}},
                    }
                ]
            }
        )
        event = to_source_change_event(notification)
        self.assertEqual(event.event_type, 'created')
        self.assertEqual(event.provider, 's3')
        self.assertEqual(event.source_document_id, 's3://b/a.txt')
        self.assertEqual(event.uri, event.source_document_id)

    def test_s3_object_removed_normalizes_to_deleted(self):
        [notification] = parse_s3_event_notifications(
            {
                'Records': [
                    {
                        'eventName': 'ObjectRemoved:Delete',
                        's3': {'bucket': {'name': 'b'}, 'object': {'key': 'a.txt'}},
                    }
                ]
            }
        )
        event = to_source_change_event(notification)
        self.assertEqual(event.event_type, 'deleted')

    def test_azure_blob_created_normalizes_to_created(self):
        notification = parse_azure_blob_event(
            {
                'eventType': 'Microsoft.Storage.BlobCreated',
                'subject': '/blobServices/default/containers/c/blobs/a.txt',
            }
        )
        event = to_source_change_event(notification)
        self.assertEqual(event.event_type, 'created')
        self.assertEqual(event.provider, 'azure-blob')
        self.assertEqual(event.source_document_id, 'azure-blob://c/a.txt')

    def test_azure_blob_deleted_normalizes_to_deleted(self):
        notification = parse_azure_blob_event(
            {
                'eventType': 'Microsoft.Storage.BlobDeleted',
                'subject': '/blobServices/default/containers/c/blobs/a.txt',
            }
        )
        event = to_source_change_event(notification)
        self.assertEqual(event.event_type, 'deleted')

    def test_carries_the_event_id_through_for_deduplication(self):
        [notification] = parse_s3_event_notifications(
            {
                'Records': [
                    {
                        'eventName': 'ObjectCreated:Put',
                        's3': {
                            'bucket': {'name': 'b'},
                            'object': {'key': 'a.txt', 'sequencer': 'seq-1'},
                        },
                    }
                ]
            }
        )
        event = to_source_change_event(notification)
        self.assertEqual(event.event_id, 'seq-1')


def _state_response(value):
    response = mock.Mock()
    response.data = None if value is None else json.dumps(value).encode('utf-8')
    return response


class EventDeduplicatorTest(unittest.TestCase):
    def setUp(self):
        self.dapr_client = mock.Mock()
        self.dapr_client.get_state.return_value = _state_response(None)
        self.deduplicator = EventDeduplicator(
            state_store_name='statestore', dapr_client=self.dapr_client
        )

    def test_an_unseen_event_is_not_already_seen(self):
        self.assertFalse(self.deduplicator.already_seen('event-1'))

    def test_marking_an_event_seen_makes_it_report_as_seen(self):
        self.deduplicator.mark_seen('event-1')
        self.dapr_client.get_state.return_value = _state_response(1)
        self.assertTrue(self.deduplicator.already_seen('event-1'))

    def test_mark_seen_sets_a_ttl(self):
        deduplicator = EventDeduplicator(
            state_store_name='statestore', dapr_client=self.dapr_client, ttl_seconds=60
        )
        deduplicator.mark_seen('event-1')
        self.assertEqual(
            self.dapr_client.save_state.call_args.kwargs['state_metadata']['ttlInSeconds'], '60'
        )

    def test_close_only_closes_an_owned_client(self):
        self.deduplicator.close()
        self.dapr_client.close.assert_not_called()

        with mock.patch('dapr.ext.rag.triggers.DaprClient') as mock_client_cls:
            owned = EventDeduplicator(state_store_name='statestore')
            owned.close()
            mock_client_cls.return_value.close.assert_called_once()


if __name__ == '__main__':
    unittest.main()
