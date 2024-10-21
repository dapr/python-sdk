# Example - Publish and subscribe to messages

This example utilizes a publisher and a subscriber to show the bidirectional pubsub pattern.
It creates a publisher and calls the `publish_event` method in the `DaprClient`.
In the s`subscriber.py` file it creates a subscriber object that can call the `next_message` method to get new messages from the stream. After processing the new message, it returns a status to the stream.


> **Note:** Make sure to use the latest proto bindings

## Pre-requisites

- [Dapr CLI and initialized environment](https://docs.dapr.io/getting-started)
- [Install Python 3.8+](https://www.python.org/downloads/)

## Install Dapr python-SDK

<!-- Our CI/CD pipeline automatically installs the correct version, so we can skip this step in the automation -->

```bash
pip3 install dapr
```

## Run example where users control reading messages off the stream

Run the following command in a terminal/command prompt:

<!-- STEP
name: Run subscriber
expected_stdout_lines:
    - "== APP == Processing message: {'id': 1, 'message': 'hello world'} from TOPIC_A1..."
    - "== APP == Processing message: {'id': 2, 'message': 'hello world'} from TOPIC_A1..."
    - "== APP == Processing message: {'id': 3, 'message': 'hello world'} from TOPIC_A1..."
    - "== APP == Processing message: {'id': 4, 'message': 'hello world'} from TOPIC_A1..."
    - "== APP == Processing message: {'id': 5, 'message': 'hello world'} from TOPIC_A1..."
    - "== APP == Closing subscription..."
output_match_mode: substring
background: true
match_order: none
sleep: 3 
-->

```bash
# 1. Start Subscriber
dapr run --app-id python-subscriber --app-protocol grpc -- python3 subscriber.py  --topic=TOPIC_A1
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
output_match_mode: substring
sleep: 15
-->

```bash
# 2. Start Publisher
dapr run --app-id python-publisher --app-protocol grpc --dapr-grpc-port=3500 --enable-app-health-check -- python3 publisher.py --topic=TOPIC_A1
```

<!-- END_STEP -->

## Run example with a handler function

Run the following command in a terminal/command prompt:

<!-- STEP
name: Run subscriber
expected_stdout_lines:
    - "== APP == Processing message: {'id': 1, 'message': 'hello world'} from TOPIC_A2..."
    - "== APP == Processing message: {'id': 2, 'message': 'hello world'} from TOPIC_A2..."
    - "== APP == Processing message: {'id': 3, 'message': 'hello world'} from TOPIC_A2..."
    - "== APP == Processing message: {'id': 4, 'message': 'hello world'} from TOPIC_A2..."
    - "== APP == Processing message: {'id': 5, 'message': 'hello world'} from TOPIC_A2..."
    - "== APP == Closing subscription..."
output_match_mode: substring
background: true
match_order: none
sleep: 3 
-->

```bash
# 1. Start Subscriber
dapr run --app-id python-subscriber --app-protocol grpc -- python3 subscriber-handler.py  --topic=TOPIC_A2
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
output_match_mode: substring
sleep: 15
-->

```bash
# 2. Start Publisher
dapr run --app-id python-publisher --app-protocol grpc --dapr-grpc-port=3500 --enable-app-health-check -- python3 publisher.py  --topic=TOPIC_A2
```

<!-- END_STEP --> 

## Cleanup


