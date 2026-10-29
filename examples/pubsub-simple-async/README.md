# Example - Publish and subscribe to messages with an asyncio gRPC app

This example is the asyncio counterpart of [`pubsub-simple`](../pubsub-simple). The subscriber
uses `dapr.ext.grpc.aio.App`, which runs a `grpc.aio` server so `@app.subscribe` handlers can be
`async def` and are awaited. The publisher uses the async `dapr.aio.clients.DaprClient`.

If you want async pub/sub without running a callback server, see
[`pubsub-streaming-async`](../pubsub-streaming-async) instead — that example uses the client-side
streaming subscription API, where your code pulls messages. This example is the server-side
callback model, where Dapr delivers messages to handlers you register.

> **Note:** Make sure to use the latest proto bindings

## Pre-requisites

- [Dapr CLI and initialized environment](https://docs.dapr.io/getting-started)
- [Install Python 3.10+](https://www.python.org/downloads/)

## Install Dapr python-SDK

<!-- Our CI/CD pipeline automatically installs the correct version, so we can skip this step in the automation -->

```bash
pip3 install "dapr[grpc]"
```

## Run the example

Run the following command in a terminal/command prompt:

<!-- STEP
name: Run subscriber
expected_stdout_lines:
  - 'Subscriber received: id=1, message="hello world", content_type="application/json"'
  - 'Subscriber received: id=2, message="hello world", content_type="application/json"'
  - 'Subscriber received: id=3, message="hello world", content_type="application/json"'
  - 'Other-Subscriber received: id=4, message="hello world", content_type="application/json"'
  - 'Subscriber received: id=20, message="bulk event 1", content_type="application/json"'
  - 'Subscriber received: id=21, message="bulk event 2", content_type="application/json"'
  - 'Subscriber received: id=22, message="bulk event 3", content_type="application/json"'
output_match_mode: substring
background: true
match_order: none
sleep: 5
-->

```bash
# 1. Start Subscriber (expose gRPC server receiver on port 13551)
dapr run --app-id python-subscriber --app-protocol grpc --app-port 13551 --enable-app-health-check --app-health-probe-interval 1 -- python3 subscriber.py
```

<!-- END_STEP -->

In another terminal/command prompt run:

<!-- STEP
name: Run publisher
expected_stdout_lines:
  - "{'id': 1, 'message': 'hello world'}"
  - "{'id': 2, 'message': 'hello world'}"
  - "{'id': 3, 'message': 'hello world'}"
  - "{'id': 4, 'message': 'hello world'}"
  - 'Bulk published 3 events. Failed entries: 0'
output_match_mode: substring
background: true
sleep: 15
-->

```bash
# 2. Start Publisher
dapr run --app-id python-publisher --app-protocol grpc -- python3 publisher.py
```

<!-- END_STEP -->

## Cleanup

<!-- STEP
expected_stdout_lines:
  - '✅  app stopped successfully: python-subscriber'
name: Shutdown dapr
-->

```bash
dapr stop --app-id python-subscriber
```

<!-- END_STEP -->

## The difference from `pubsub-simple`

Only the import and the way the app is started change:

```diff
-from dapr.ext.grpc import App, SubscriptionMessage
-from dapr.clients.grpc._response import TopicEventResponse
+from dapr.ext.grpc.aio import App, SubscriptionMessage, TopicEventResponse

 app = App()

 @app.subscribe(pubsub_name='pubsub', topic='TOPIC_A')
-def mytopic(event: SubscriptionMessage) -> TopicEventResponse:
+async def mytopic(event: SubscriptionMessage) -> TopicEventResponse:
     ...

-app.run(13551)
+asyncio.run(app.run(13551))
```

Handlers keep returning `TopicEventResponse('success' | 'retry' | 'drop')`, and topic rules,
dead letter topics, bulk delivery and `disable_topic_validation` all behave exactly as they do
on the synchronous app.
