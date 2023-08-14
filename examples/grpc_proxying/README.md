# Example - Add an existing gRPC service to the Python SDK gRPC App extension

This example creates a gRPC service using the protobuf file and adds it to the Python SDK gRPC App extension. Using add_external_service, we can add the `HelloWorld` servicer. This way we can use gRPC Proxying feature of Dapr and at the same time have a full access to other features that come with Python SDK, such as pubsub.

> **Note:** Make sure to use the latest proto bindings

## Pre-requisites

- [Dapr CLI and initialized environment](https://docs.dapr.io/getting-started)
- [Install Python 3.8+](https://www.python.org/downloads/)

## Install Dapr python-SDK

<!-- Our CI/CD pipeline automatically installs the correct version, so we can skip this step in the automation -->

```bash
pip3 install dapr dapr-ext-grpc
```

## Running in self-hosted mode

Run the following command in a terminal/command-prompt:

<!-- STEP 
name: Run receiver
expected_stdout_lines:
  - '== APP == INFO:root:name: "you"'
background: true
sleep: 5
-->

```bash
# 1. Start Receiver (expose gRPC server receiver on port 50051)
dapr run --app-id  invoke-receiver --app-protocol grpc --app-port 50051 --config config.yaml -- python  invoke-receiver.py
```

<!-- END_STEP -->

In another terminal/command prompt run:


<!-- STEP
name: Run caller
expected_stdout_lines:
  - '== APP == Greeter client received: Hello, you!'
background: true
sleep: 5 
-->


```bash
# 2. Start Caller
dapr run --app-id  invoke-caller --dapr-grpc-port 50007 --config config.yaml -- python  invoke-caller.py
```

<!-- END_STEP -->

## Cleanup

<!-- STEP
expected_stdout_lines: 
  - '✅  app stopped successfully: invoke-receiver'
name: Shutdown dapr
-->

```bash
dapr stop --app-id  invoke-receiver
```

<!-- END_STEP -->

## Running in Kubernetes mode

1. Build docker image

   ```
   docker build -t [your registry]/invokegrpcproxy:latest .
   ```

2. Push docker image

   ```
   docker push [your registry]/invokegrpcproxy:latest
   ```

3. Edit image name to `[your registry]/invokegrpcproxy:latest` in deploy/*.yaml

4. Deploy applications

   ```
   kubectl apply -f ./deploy/
   ```

5. See logs for the apps and sidecars

   Logs for caller sidecar:
   ```
   dapr  logs -a invoke-caller -k
   ```
   
   Logs for caller app:
   ```
   kubectl logs -l app="invokecaller" -c invokecaller
   ```
   
   Logs for receiver sidecar:
   ```
   dapr  logs -a invoke-receiver -k
   ```
   
   Logs for receiver app:
   ```
   kubectl logs -l app="invokereceiver" -c invokereceiver
   ```
