# Example - Pub/Sub

This example utilizes a publisher and a subscriber to show the pubsub pattern, it also shows `OnTopicEvent` and `GetTopicSubscriptions` functionality.
It will create a gRPC subscriber and bind the `OnTopicEvent` method, which gets triggered after a message is published to the subscribed topic.

> **Note:** Make sure to use the latest proto bindings

## Running

To run this example, the following code can be utilized:

```bash
# 1. Start Subscriber (expose gRPC server receiver on port 50051)
dapr run --app-id python-subscriber --protocol grpc --app-port 50051 python subscriber.py

# 2. Start Publisher
dapr run --app-id python-publisher --protocol grpc python publisher.py
```