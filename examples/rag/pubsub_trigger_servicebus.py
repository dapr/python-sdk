# -*- coding: utf-8 -*-
# Copyright 2026 The Dapr Authors
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#     http://www.apache.org/licenses/LICENSE-2.0
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""The Azure-native event path: Blob change -> Event Grid -> Service Bus -> Dapr pub/sub -> here.

    Azure Blob Storage (BlobCreated/BlobDeleted)
        -> Event Grid system topic
        -> Event Grid subscription targeting a Service Bus topic
        -> Dapr Azure Service Bus Topics pub/sub component (examples/rag/components/azure/servicebus-pubsub.yaml)
        -> this subscriber

See `examples/rag/infra/main.bicep` for provisioning the Event Grid system
topic + subscription and the Service Bus namespace/topic, and
`docs/rag/azure-rbac.md` for the identity this process needs (Service Bus
data-receive only -- see that doc for why it must not have any Search/OpenAI/
Storage-write permissions).

Event Grid delivers in either its own schema or CloudEvents schema; both are
handled by `triggers.parse_azure_blob_event`. Duplicate and out-of-order
delivery are handled the same way as the S3 path (see pubsub_trigger.py) --
by `EventDeduplicator` plus debounced reconciliation, since delivery order
and exactly-once are never guaranteed.

    dapr run --app-id rag-azure-trigger --resources-path components/ --app-port 6002 -- python3 pubsub_trigger_servicebus.py
"""

from __future__ import annotations

import logging

from config import build_pipeline_id, build_state_store_name
from reconciliation_workflow import ReconciliationTrigger

from dapr.ext.grpc import App, SubscriptionMessage, TopicEventResponse
from dapr.ext.rag.triggers import EventDeduplicator, parse_azure_blob_event, to_source_change_event

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger('rag-azure-trigger')

app = App()
deduplicator = EventDeduplicator(state_store_name=build_state_store_name())
reconciliation = ReconciliationTrigger(pipeline_id=build_pipeline_id())


@app.subscribe(
    pubsub_name='rag-events-pubsub', topic='blob-events'
)  # matches infra/main.bicep's serviceBusTopicName
def on_blob_event(message: SubscriptionMessage) -> TopicEventResponse:
    payload = message.data()
    notification = parse_azure_blob_event(payload)
    if notification is None:
        logger.warning('Received a message that is not a recognizable blob event; ignoring.')
        return TopicEventResponse('success')

    event = to_source_change_event(notification)
    if deduplicator.already_seen(event.event_id):
        logger.info('Duplicate delivery of event_id=%s; skipping.', event.event_id)
        return TopicEventResponse('success')

    deduplicator.mark_seen(event.event_id)
    logger.info(
        'source_document_id=%s event_type=%s -- scheduling a debounced reconciliation',
        event.source_document_id,
        event.event_type,
    )
    reconciliation.notify_change(event)
    return TopicEventResponse('success')


if __name__ == '__main__':
    app.run(6002)
