# Example - Publish Actor to messages with PubSub

This example utilizes a publisher and a subscriber to show the pubsub actor pattern, it also shows `PublishActorEvent`, `OnTopicEvent`, and `GetTopicSubscriptions` functionality.
It creates a publisher and calls the `publish_actor_event` method in the `DaprClient`.
It will create a http subscriber and receive the cloud event as a JSON, which gets triggered after a message is published to the subscribed topic.

> **Note:** Make sure to use the latest proto bindings

## Pre-requisites

- [Dapr CLI and initialized environment](https://docs.dapr.io/getting-started)
- [Install Python 3.7+](https://www.python.org/downloads/)

## Install Dapr python-SDK

<!-- Our CI/CD pipeline automatically installs the correct version, so we can skip this step in the automation -->

```bash
pip3 install dapr dapr-ext-grpc
pip3 install flask_dapr
```

## Run the example

Run the following command in a terminal/command prompt:

<!-- STEP
name: Run subscriber
expected_stdout_lines:
  - '== APP == Subscriber received ActorID: Actor1'
  - '== APP == Subscriber received ActorType: MyActorType'
  - '== APP == Subscriber received Message: Good morning'
  - '== APP == Subscriber received ActorID: Actor2'
  - '== APP == Subscriber received ActorType: MyActorType'
  - '== APP == Subscriber received Message: Good day'
  - '== APP == Subscriber received ActorID: Actor3'
  - '== APP == Subscriber received ActorType: MyActorType'
  - '== APP == Subscriber received Message: Good night'
output_match_mode: substring
background: true
sleep: 3
timeout_seconds: 30
-->

```bash
# 1. Start Subscriber (expose http server receiver on port 3501)
dapr run --app-id python-actor-subscriber --app-protocol http --app-port 5000 --dapr-http-port 3501 -- python3 actor_subscriber.py
```

<!-- END_STEP -->

In another terminal/command prompt run:

<!-- STEP
name: Run publisher
expected_stdout_lines:
  - "== APP == {'id': 1, 'message': 'Good morning'}"
  - "== APP == {'id': 2, 'message': 'Good day'}"
  - "== APP == {'id': 3, 'message': 'Good night'}"
background: true
sleep: 6
-->

```bash
# 2. Start Publisher
dapr run --app-id python-publisher --app-protocol grpc --dapr-grpc-port=5500 python3 actor_publisher.py
```

<!-- END_STEP -->

## Cleanup

<!-- STEP
expected_stdout_lines: 
  - '✅  app stopped successfully: python-actor-subscriber'
expected_stderr_lines:
name: Shutdown dapr
-->

```bash
dapr stop --app-id python-actor-subscriber
```

<!-- END_STEP -->
