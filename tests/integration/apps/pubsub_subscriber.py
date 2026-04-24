"""Pub/sub subscriber that persists received messages to state store.

Used by integration tests to verify message delivery without relying on stdout.
"""

import json

from cloudevents.sdk.event import v1
from dapr.ext.grpc import App

from dapr.clients import DaprClient
from dapr.clients.grpc._response import TopicEventResponse

app = App()


@app.subscribe(pubsub_name='pubsub', topic='TOPIC_A')
def handle_topic_a(event: v1.Event) -> TopicEventResponse:
    data = json.loads(event.Data())
    key = f'received-{data["run_id"]}-{data["id"]}'
    with DaprClient() as d:
        d.save_state('statestore', key, event.Data())
    return TopicEventResponse('success')


app.run(50051)
