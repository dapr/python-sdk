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

"""One example of entering ingestion through Dapr pub/sub: S3 Event Notifications.

Wires S3 -> (SNS/SQS or EventBridge) -> a Dapr pub/sub component -> this
subscriber, which normalizes the event (triggers.py) and reconciles the
affected prefix. See `reconciliation_workflow.py` for why this debounces
rather than starting a new ingestion run per event, and
`pubsub_trigger_servicebus.py` for the Azure Blob equivalent.

This is deliberately the *one* transport shown for S3, per the MVP's scope
("one clear example per provider is sufficient") -- adapt the pub/sub
component (SNS->SQS, or EventBridge->SQS) to your own AWS setup; only the
Dapr-side subscriber and payload shape need to match.

    dapr run --app-id rag-s3-trigger --resources-path components/ --app-port 6001 -- python3 pubsub_trigger.py
"""

from __future__ import annotations

import logging

from config import build_pipeline_id, build_state_store_name
from reconciliation_workflow import ReconciliationTrigger

from dapr.ext.grpc import App, SubscriptionMessage, TopicEventResponse
from dapr.ext.rag.triggers import (
    EventDeduplicator,
    parse_s3_event_notifications,
    to_source_change_event,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger('rag-s3-trigger')

app = App()
deduplicator = EventDeduplicator(state_store_name=build_state_store_name())
reconciliation = ReconciliationTrigger(pipeline_id=build_pipeline_id())


@app.subscribe(pubsub_name='rag-events-pubsub', topic='s3-object-events')
def on_s3_event(message: SubscriptionMessage) -> TopicEventResponse:
    payload = message.data()
    notifications = parse_s3_event_notifications(payload)
    if not notifications:
        logger.warning('Received a message with no recognizable S3 event Records; ignoring.')
        return TopicEventResponse('success')

    for notification in notifications:
        event = to_source_change_event(notification)
        if deduplicator.already_seen(event.event_id):
            logger.info('Duplicate delivery of event_id=%s; skipping.', event.event_id)
            continue
        deduplicator.mark_seen(event.event_id)
        logger.info(
            'source_document_id=%s event_type=%s -- scheduling a debounced reconciliation',
            event.source_document_id,
            event.event_type,
        )
        reconciliation.notify_change(event)

    return TopicEventResponse('success')


if __name__ == '__main__':
    app.run(6001)
