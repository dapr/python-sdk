"""Pub/sub subscriber that persists received messages to state store.

Used by integration tests to verify message delivery without relying on stdout.
"""

from dapr.clients import DaprClient
from dapr.clients.grpc._response import TopicEventResponse
from dapr.ext.grpc import App, SubscriptionMessage

app = App()


@app.subscribe(pubsub_name='pubsub', topic='TOPIC_A')
def handle_topic_a(event: SubscriptionMessage) -> TopicEventResponse:
    data = event.data()
    key = f'received-{data["run_id"]}-{data["id"]}'
    with DaprClient() as d:
        d.save_state('statestore', key, event.raw_data())
    return TopicEventResponse('success')


app.run(13503)
