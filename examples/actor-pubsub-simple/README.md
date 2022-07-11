# Example - Publish Actor to messages with PubSub

This example utilizes a publisher and a subscriber to show the pubsub actor pattern, it also shows `PublishActorEvent`, `OnTopicEvent`, `GetTopicSubscriptions`, and `TopicEventResponse` functionality.
It creates a publisher and calls the `publish_actor_event` method in the `DaprClient`.
It will create a gRPC subscriber and bind the `OnTopicEvent` method, which gets triggered after a message is published to the subscribed topic.
The subscriber will tell dapr to retry delivery of the first message it receives, logging that the message will be retried, and printing it at least once to standard output.

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
  - '== APP == Dapr pub/sub is subscribed to: [{"pubsubname": "pubsub", "topic": "mytopic", "route": "endpoint"}]'
  - '== APP == Subscriber received ActorID: Actor0'
  - '== APP == Subscriber received ActorType: fakeActorType'
  - '== APP == Subscriber received Message: Hello message'
  - '== APP == Subscriber received ActorID: Actor1'
  - '== APP == Subscriber received ActorType: fakeActorType'
  - '== APP == Subscriber received Message: Hello message'
  - '== APP == Subscriber received ActorID: Actor2'
  - '== APP == Subscriber received ActorType: fakeActorType'
  - '== APP == Subscriber received Message: Hello message'
output_match_mode: substring
background: true
sleep: 3 
-->

```bash
# 1. Start Subscriber (expose gRPC server receiver on port 50051)
dapr run --app-id python-actor-subscriber --app-protocol http --app-port 5000 -- python3 actor_subscriber.py
```

<!-- END_STEP -->

In another terminal/command prompt run:

<!-- STEP
name: Run publisher
expected_stdout_lines:
  - "== APP == {'message': 'Hello message'}"
  - "== APP == {'message': 'Hello message'}"
  - "== APP == {'message': 'Hello message'}"
background: true
sleep: 6
-->

```bash
# 2. Start Publisher
dapr run --app-id python-actor-publisher --app-protocol http --app-port 3500 -- python3 actor_publisher.py
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
