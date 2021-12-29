# Example - Get Configuration

This example demonstrates the Configuration APIs in Dapr.
It demonstrates the following APIs:
- **configuration**: Get configuration from statestore

> **Note:** Make sure to use the latest proto bindings

## Pre-requisites

- [Dapr CLI and initialized environment](https://docs.dapr.io/getting-started)
- [Install Python 3.7+](https://www.python.org/downloads/)

## Install Dapr python-SDK

<!-- Our CI/CD pipeline automatically installs the correct version, so we can skip this step in the automation -->
```bash
pip3 install dapr dapr-ext-grpc
```

## Store the configuration in configurationstore 
<!-- STEP
name: Set configuration value
expected_stdout_lines:
  - "OK"
timeout_seconds: 5
-->

```bash
docker exec -it dapr_redis redis-cli SET greeting "hello world||1"
```

<!-- END_STEP -->

## Run the example

Change directory to this folder:
```bash
cd examples/configuration
```

To run this example, use the following command:

<!-- STEP
name: Run get configuration example
expected_stdout_lines:
  - "== APP == Got key=greeting value=hello world version=1"
timeout_seconds: 5
-->

```bash
dapr run --app-id configexample --components-path components/ -- python3 configuration.py
```
<!-- END_STEP -->

You should be able to see the following output:
```
== APP == Got key=greeting value=hello world version=1
```

## Cleanup

Either press CTRL + C to quit the app or run the following command in a new terminal to stop the app
```bash
dapr stop --app-id=configexample
```
