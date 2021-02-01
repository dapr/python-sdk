# Example - Publish and subscribe to messages

This example utilizes a publisher and a subscriber to show the pubsub pattern, it also shows `PublishEvent`, `OnTopicEvent` and `GetTopicSubscriptions` functionality. 
It creates a publisher and calls the `publish_event` method in the `DaprClient`.
It will create a gRPC subscriber and bind the `OnTopicEvent` method, which gets triggered after a message is published to the subscribed topic.

> **Note:** Make sure to use the latest proto bindings

## Pre-requisites

- [Dapr CLI and initialized environment](https://docs.dapr.io/getting-started)
- [Install Python 3.7+](https://www.python.org/downloads/)

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
  - '== APP == Subscriber received: id=2, message="hello world", content_type="application/json"'
  - '== APP == Subscriber received: id=3, message="hello world", content_type="application/json"'
  - '== APP == Subscriber received: id=4, message="hello world", content_type="application/json"'
  - '== APP == Subscriber received: id=5, message="hello world", content_type="application/json"'
background: true
sleep: 5 
-->

```bash
# 1. Start Subscriber (expose gRPC server receiver on port 50051)
dapr run --app-id python-subscriber --app-protocol grpc --app-port 50051 python3 subscriber.py
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
background: true
sleep: 15
-->

```bash
# 2. Start Publisher
dapr run --app-id python-publisher --app-protocol grpc --dapr-grpc-port=3500 python3 publisher.py
```

<!-- END_STEP -->

## Cleanup

<!-- STEP
expected_stdout_lines: 
  - '✅  app stopped successfully: python-publisher'
  - '✅  app stopped successfully: python-subscriber'
expected_stderr_lines:
name: Shutdown dapr
-->

```bash
dapr stop --app-id python-publisher
dapr stop --app-id python-subscriber
```

<!-- END_STEP -->
