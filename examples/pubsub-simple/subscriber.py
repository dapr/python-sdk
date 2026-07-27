# ------------------------------------------------------------
# Copyright 2022 The Dapr Authors
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#     http://www.apache.org/licenses/LICENSE-2.0
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
# ------------------------------------------------------------

from time import sleep

from dapr.clients.grpc._response import TopicEventResponse
from dapr.ext.grpc import App, SubscriptionMessage
from dapr.proto import appcallback_v1

# Handlers annotated with SubscriptionMessage receive that type. Unannotated handlers
# receive the deprecated cloudevents.sdk.event.v1.Event and a DeprecationWarning.
app = App()
should_retry = True  # To control whether dapr should retry sending a message


@app.subscribe(pubsub_name='pubsub', topic='TOPIC_A')
def mytopic(event: SubscriptionMessage) -> TopicEventResponse:
    global should_retry
    # event.data() is already parsed based on the content type (dict for application/json)
    data = event.data()
    print(
        f'Subscriber received: id={data["id"]}, message="{data["message"]}", '
        f'content_type="{event.data_content_type()}"',
        flush=True,
    )
    # event.extensions() contains the cloud event extensions and
    # event.metadata() the delivery metadata
    if should_retry:
        should_retry = False  # we only retry once in this example
        sleep(0.5)  # add some delay to help with ordering of expected logs
        return TopicEventResponse('retry')
    return TopicEventResponse('success')


@app.subscribe(pubsub_name='pubsub', topic='TOPIC_CE')
def receive_cloud_events(event: SubscriptionMessage) -> TopicEventResponse:
    print('Subscriber received: ' + event.topic(), flush=True)

    content_type = event.data_content_type()
    # event.data() is parsed by content type: dict for JSON, str for plain text
    data = event.data()

    try:
        if content_type == 'application/json':
            print(
                f'Subscriber received a json cloud event: id={data["id"]}, message="{data["message"]}", '
                f'content_type="{content_type}"',
                flush=True,
            )
        elif content_type == 'text/plain':
            print(
                f'Subscriber received plain text cloud event: {data}, '
                f'content_type="{content_type}"',
                flush=True,
            )
        else:
            print(f'Received unknown content type: {content_type}', flush=True)
            return TopicEventResponse('fail')

    except Exception as e:
        print('Failed to process event data:', e, flush=True)
        return TopicEventResponse('fail')

    return TopicEventResponse('success')


@app.subscribe(pubsub_name='pubsub', topic='TOPIC_D', dead_letter_topic='TOPIC_D_DEAD')
def fail_and_send_to_dead_topic(event: SubscriptionMessage) -> TopicEventResponse:
    return TopicEventResponse('retry')


@app.subscribe(pubsub_name='pubsub', topic='TOPIC_D_DEAD')
def mytopic_dead(event: SubscriptionMessage) -> TopicEventResponse:
    data = event.data()
    print(
        f'Dead-Letter Subscriber received: id={data["id"]}, message="{data["message"]}", '
        f'content_type="{event.data_content_type()}"',
        flush=True,
    )
    print('Dead-Letter Subscriber. Received via deadletter topic: ' + event.topic(), flush=True)
    print(
        'Dead-Letter Subscriber. Originally intended topic: ' + event.extensions()['topic'],
        flush=True,
    )
    return TopicEventResponse('success')


# == for testing with Redis only ==
# workaround as redis pubsub does not support wildcards
# we manually register the distinct topics
for id in range(4, 7):
    app._servicer._registered_topics.append(
        appcallback_v1.TopicSubscription(pubsub_name='pubsub', topic=f'topic/{id}')
    )
# =================================


# this allows subscribing to all events sent to this app - useful for wildcard topics
@app.subscribe(pubsub_name='pubsub', topic='topic/#', disable_topic_validation=True)
def mytopic_wildcard(event: SubscriptionMessage) -> TopicEventResponse:
    data = event.data()
    print(
        f'Wildcard-Subscriber received: id={data["id"]}, message="{data["message"]}", '
        f'content_type="{event.data_content_type()}"',
        flush=True,
    )
    return TopicEventResponse('success')


# Example of an unhealthy status
# def unhealthy():
#     raise ValueError("Not healthy")
# app.register_health_check(unhealthy)

app.register_health_check(lambda: print('Healthy'))

app.run(13551)
