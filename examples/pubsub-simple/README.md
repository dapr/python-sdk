# Example - Publish and subscribe to messages

This example utilizes a publisher and a subscriber to show the pubsub pattern, it also shows `PublishEvent`, `PublishEvents` (bulk), `OnTopicEvent`, `GetTopicSubscriptions`, and `TopicEventResponse` functionality.
It creates a publisher and calls the `publish_event` and `publish_events` methods in the `DaprClient`.
It will create a gRPC subscriber and bind the `OnTopicEvent` method, which gets triggered after a message is published to the subscribed topic.
The subscriber will tell dapr to retry delivery of the first message it receives, logging that the message will be retried, and printing it at least once to standard output.

> **Note:** Make sure to use the latest proto bindings

## Pre-requisites

- [Dapr CLI and initialized environment](https://docs.dapr.io/getting-started)
- [Install Python 3.9+](https://www.python.org/downloads/)

## Install Dapr python-SDK

<!-- Our CI/CD pipeline automatically installs the correct version, so we can skip this step in the automation -->

```bash
pip3 install dapr dapr-ext-grpc
```

## Run the example

Run the following command in a terminal/command prompt:

<!-- STEP
name: Run subscriber
expected_stdout_lines:
  - '== APP == Subscriber received: id=1, message="hello world", content_type="application/json"'
  - 'RETRY status returned from app while processing pub/sub event'
  - '== APP == Subscriber received: id=2, message="hello world", content_type="application/json"'
  - '== APP == Subscriber received: id=3, message="hello world", content_type="application/json"'
  - '== APP == Wildcard-Subscriber received: id=4, message="hello world", content_type="application/json"'
  - '== APP == Wildcard-Subscriber received: id=5, message="hello world", content_type="application/json"'
  - '== APP == Wildcard-Subscriber received: id=6, message="hello world", content_type="application/json"'
  - '== APP == Dead-Letter Subscriber received: id=7, message="hello world", content_type="application/json"'
  - '== APP == Dead-Letter Subscriber. Received via deadletter topic: TOPIC_D_DEAD'
  - '== APP == Dead-Letter Subscriber. Originally intended topic: TOPIC_D'
  - '== APP == Subscriber received: TOPIC_CE'
  - '== APP == Subscriber received a json cloud event: id=8, message="hello world", content_type="application/json"'
  - '== APP == Subscriber received: id=20, message="bulk event 1", content_type="application/json"'
  - '== APP == Subscriber received: id=21, message="bulk event 2", content_type="application/json"'
  - '== APP == Subscriber received: id=22, message="bulk event 3", content_type="application/json"'
  - '== APP == Subscriber received: TOPIC_CE'
  - '== APP == Subscriber received plain text cloud event: hello world, content_type="text/plain"'
    
output_match_mode: substring
background: true
match_order: none
sleep: 3 
-->

```bash
# 1. Start Subscriber (expose gRPC server receiver on port 50051)
dapr run --app-id python-subscriber --app-protocol grpc --app-port 50051 -- python3 subscriber.py
```

<!-- END_STEP -->

In another terminal/command prompt run:

<!-- STEP
name: Run publisher
expected_stdout_lines:
  - "== APP == {'id': 1, 'message': 'hello world'}"
  - "== APP == {'id': 2, 'message': 'hello world'}"
  - "== APP == {'id': 3, 'message': 'hello world'}"
  - "== APP == {'id': 4, 'message': 'hello world'}"
  - "== APP == {'id': 5, 'message': 'hello world'}"
  - "== APP == {'id': 6, 'message': 'hello world'}"
  - "== APP == {'id': 7, 'message': 'hello world'}"
  - "== APP == {'specversion': '1.0', 'type': 'com.example.event', 'source': 'my-service', 'id': 'abc-8', 'data': {'id': 8, 'message': 'hello world'}, 'datacontenttype': 'application/json'}"
  - "== APP == Bulk published 3 events. Failed entries: 0"
  - "== APP == {'specversion': '1.0', 'type': 'com.example.event', 'source': 'my-service', 'id': 'abc-10', 'data': 'hello world', 'datacontenttype': 'text/plain'}"
background: true
sleep: 15
-->

```bash
# 2. Start Publisher
dapr run --app-id python-publisher --app-protocol grpc --dapr-grpc-port=3500 --enable-app-health-check python3 publisher.py
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
