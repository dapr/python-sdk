# Example - Invoke a service

This example utilizes a receiver and a caller for the `invoke_method` functionality.

> **Note:** Make sure to use the latest proto bindings

## Pre-requisites

- [Dapr CLI and initialized environment](https://docs.dapr.io/getting-started)
- [Install Python 3.8+](https://www.python.org/downloads/)

### Install requirements

You can install dapr SDK package using pip command:

<!-- STEP 
name: Install requirements
-->

```sh
pip3 install dapr Flask
```

<!-- END_STEP -->

## Run the example

To run this example, the following code can be utilized:

Start the receiver:
<!-- STEP
name: Run invoke http example
expected_stdout_lines:
  - '== APP == Order received : {"id": 1, "message": "hello world"}'
  - '== APP == Order error : {"id": 2, "message": "hello world"}'
background: true
sleep: 5
-->

```bash
dapr run --app-id=invoke-receiver --app-port=8088 --app-protocol http -- python3 invoke-receiver.py
```
<!-- END_STEP -->

Start the caller:
<!-- STEP
name: Run invoke http example
expected_stdout_lines:
  - '== APP == text/html'
  - '== APP == {"success": true}'
  - '== APP == 200'
  - '== APP == error occurred'
  - '== APP == MY_CODE'
  - '== APP == {"message": "error occurred", "errorCode": "MY_CODE"}'
  - '== APP == 503'
  - '== APP == Internal Server Error'
background: true
sleep: 5 
-->

```bash
dapr run --app-id=invoke-caller -- python3 invoke-caller.py
```
<!-- END_STEP -->

## Cleanup

<!-- STEP
expected_stdout_lines: 
  - '✅  app stopped successfully: invoke-receiver'
name: Shutdown dapr
-->

```bash
dapr stop --app-id invoke-receiver
```

<!-- END_STEP -->