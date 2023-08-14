# Example - Invoke a service

This example utilizes a receiver and a caller for the OnInvoke / Invoke functionality. It will create a gRPC server and bind the OnInvoke method, which gets called after a client sends a direct method invocation.

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
  - '== APP == {"id": 1, "message": "hello world"}'
  - '== APP == {"id": 1, "message": "hello world"}'
background: true
sleep: 5
-->

```bash
# 1. Start Receiver (expose gRPC server receiver on port 50051)
dapr run --app-id invoke-receiver --app-protocol grpc --app-port 50051 python3 invoke-receiver.py
```

<!-- END_STEP -->

In another terminal/command prompt run:

<!-- STEP
name: Run caller
expected_stdout_lines:
  - '== APP == text/plain'
  - '== APP == INVOKE_RECEIVED'
  - '== APP == text/plain'
  - '== APP == INVOKE_RECEIVED'
background: true
sleep: 5 
-->

```bash
# 2. Start Caller
dapr run --app-id invoke-caller --app-protocol grpc --dapr-http-port 3500 python3 invoke-caller.py
```

<!-- END_STEP -->

## Cleanup

<!-- STEP
expected_stdout_lines: 
  - '✅  app stopped successfully: invoke-caller'
  - '✅  app stopped successfully: invoke-receiver'
name: Shutdown dapr
-->

```bash
dapr stop --app-id invoke-caller
dapr stop --app-id invoke-receiver
```

<!-- END_STEP -->

## Running in Kubernetes mode

1. Build docker image

   ```
   docker build -t [your registry]/invokesimple:latest .
   ```

2. Push docker image

   ```
   docker push [your registry]/invokesimple:latest
   ```

3. Edit image name to `[your registry]/invokesimple:latest` in deploy/*.yaml

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
