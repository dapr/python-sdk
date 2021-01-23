# Example - Publish and subscribe to messages

This example utilizes a publisher and a subscriber to show the pubsub pattern, it also shows `PublishEvent`, `OnTopicEvent` and `GetTopicSubscriptions` functionality. 
It creates a publisher and calls the `publish_event` method in the `DaprClient`.
It will create a gRPC subscriber and bind the `OnTopicEvent` method, which gets triggered after a message is published to the subscribed topic.

> **Note:** Make sure to use the latest proto bindings

## Pre-requisites

- [Dapr CLI and initialized environment](https://docs.dapr.io/getting-started)
- [Install Python 3.7+](https://www.python.org/downloads/)

## Install Dapr python-SDK

```bash
pip3 install dapr dapr-ext-grpc
```

## Run the example

Run the following command in a terminal/command prompt:

```bash
# 1. Start Subscriber (expose gRPC server receiver on port 50051)
dapr run --app-id python-subscriber --app-protocol grpc --app-port 50051 python3 subscriber.py
```

In another terminal/command prompt run:

```bash
# 2. Start Publisher
dapr run --app-id python-publisher --app-protocol grpc python3 publisher.py
```