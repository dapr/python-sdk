from time import sleep
from cloudevents.sdk.event import v1
from dapr.ext.grpc import App
from dapr.clients.grpc._response import TopicEventResponse
from dapr.proto import appcallback_v1

import json

app = App()
should_retry = True  # To control whether dapr should retry sending a message


@app.subscribe(pubsub_name='pubsub', topic='TOPIC_A')
def mytopic(event: v1.Event) -> TopicEventResponse:
    global should_retry
    data = json.loads(event.Data())
    print(f'Subscriber received: id={data["id"]}, message="{data["message"]}", '
          f'content_type="{event.content_type}"', flush=True)
    if should_retry:
        should_retry = False  # we only retry once in this example
        sleep(2)  # add some delay to help with ordering of expected logs
        return TopicEventResponse('retry')
    return TopicEventResponse('success')


# workaround as redis pubsub does not support wildcards
for id in range(10):
    app._servicer._registered_topics.append(appcallback_v1.TopicSubscription(
        pubsub_name='pubsub', topic=f'topic/{id}'))


@app.subscribe(pubsub_name='pubsub', topic='topic/#', disable_topic_validation=True)
def mytopic_wildcard(event: v1.Event) -> TopicEventResponse:
    data = json.loads(event.Data())
    print(f'Wildcard-Subscriber received: id={data["id"]}, message="{data["message"]}", '
          f'content_type="{event.content_type}"', flush=True)
    return TopicEventResponse('success')


app.run(50051)
