# Example - Error handling

This guide demonstrates handling `DaprGrpcError` errors when using the Dapr python-SDK. It's important to note that not all Dapr gRPC status errors are currently captured and transformed into a `DaprGrpcError` by the SDK. Efforts are ongoing to enhance this aspect, and contributions are welcome. For detailed information on error handling in Dapr, refer to the [official documentation](https://docs.dapr.io/reference/errors/).

The example involves creating a DaprClient and invoking the save_state method. 
It uses the default configuration from Dapr init in [self-hosted mode](https://github.com/dapr/cli#install-dapr-on-your-local-machine-self-hosted). 

## Pre-requisites

- [Dapr CLI and initialized environment](https://docs.dapr.io/getting-started)
- [Install Python 3.8+](https://www.python.org/downloads/)

## Install Dapr python-SDK

<!-- Our CI/CD pipeline automatically installs the correct version, so we can skip this step in the automation -->

```bash
pip3 install dapr dapr-ext-grpc
```

## Run the example

To run this example, the following code can be used:

<!-- STEP
name: Run error handling example
expected_stdout_lines:
    - "== APP == Status code: StatusCode.INVALID_ARGUMENT"
    - "== APP == Message: input key/keyPrefix 'key||' can't contain '||'"
    - "== APP == Error code: DAPR_STATE_ILLEGAL_KEY"
    - "== APP == Error info(reason): DAPR_STATE_ILLEGAL_KEY"
    - "== APP == Resource info (resource type): state"
    - "== APP == Resource info (resource name): statestore"
    - "== APP == Bad request (field): key||"
    - "== APP == Bad request (description): input key/keyPrefix 'key||' can't contain '||'"
timeout_seconds: 5
-->

```bash
dapr run -- python3 error_handling.py
```
<!-- END_STEP -->

The output should be as follows:

```
== APP == Status code: StatusCode.INVALID_ARGUMENT
== APP == Message: input key/keyPrefix 'key||' can't contain '||'
== APP == Error code: DAPR_STATE_ILLEGAL_KEY
== APP == Error info(reason): DAPR_STATE_ILLEGAL_KEY
== APP == Resource info (resource type): state
== APP == Resource info (resource name): statestore
== APP == Bad request (field): key||
== APP == Bad request (description): input key/keyPrefix 'key||' can't contain '||'
```