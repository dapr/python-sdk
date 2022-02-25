from cloudevents.sdk.event import v1
from dapr.ext.grpc import App
from dapr.clients.grpc._response import TopicEventResponse

import json

app = App()
should_retry = True  # To control whether dapr should retry sending a message

@app.subscribe(pubsub_name='pubsub', topic='TOPIC_A')
def mytopic(event: v1.Event) -> TopicEventResponse:
    global should_retry
    data = json.loads(event.Data())
    print(f'Subscriber received: id={data["id"]}, message="{data["message"]}", content_type="{event.content_type}"',flush=True)
    if should_retry:
        should_retry = False  # we only retry once in this example
        return TopicEventResponse('retry')
    return TopicEventResponse('success')

app.run(50051)
