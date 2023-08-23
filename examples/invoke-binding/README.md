# Example - Dapr bindings

This example utilizes a publisher and a receiver for the InvokeBinding / OnBindingEvent / ListInputBindings functionality. It will create a gRPC server and bind the OnBindingEvent method, which gets called after a publisher sends a message to a kafka binding.

> **Note:** Make sure to use the latest proto bindings

## Pre-requisites

- [Dapr CLI and initialized environment](https://docs.dapr.io/getting-started)
- [Install Python 3.8+](https://www.python.org/downloads/)

## Install Dapr python-SDK

<!-- Our CI/CD pipeline automatically installs the correct version, so we can skip this step in the automation -->

```bash
pip3 install dapr dapr-ext-grpc
```

## Run example

Run the following commands in a terminal/command-prompt:

<!-- STEP
name: Kafka install
sleep: 30
-->

1. Start the kafka containers using docker-compose 

```bash
docker-compose -f ./docker-compose-single-kafka.yml up -d
```

<!-- END_STEP -->

<!-- STEP
name: Start Receiver
expected_stdout_lines: 
  - '== APP == {"id": 1, "message": "hello world"}'
  - '== APP == {"id": 2, "message": "hello world"}'
  - '== APP == {"id": 3, "message": "hello world"}'
background: true
sleep: 5
-->

2. Start Receiver (expose gRPC server receiver on port 50051) 

```bash
dapr run --app-id receiver --app-protocol grpc --app-port 50051 --resources-path ./components python3 invoke-input-binding.py
```

<!-- END_STEP -->

3. Start Publisher

In another terminal/command-prompt run:

<!-- STEP
name: Start Publisher
expected_stdout_lines: 
  - '== APP == Sending message id: 1, message "hello world"'
  - '== APP == Sending message id: 2, message "hello world"'
  - '== APP == Sending message id: 3, message "hello world"'
background: true
sleep: 5
-->

```bash
dapr run --app-id publisher --app-protocol grpc --resources-path ./components python3 invoke-output-binding.py
```

<!-- END_STEP -->

## Cleanup

<!-- STEP
name: Cleanup
expected_stdout_lines:
  - '✅  app stopped successfully: publisher'
  - '✅  app stopped successfully: receiver'
-->

The dapr apps can be stopped by calling stop or terminating the process:

```bash
dapr stop --app-id publisher
dapr stop --app-id receiver
```

For kafka cleanup, run the following code:

```bash
docker-compose -f ./docker-compose-single-kafka.yml down
```

<!-- END_STEP -->
