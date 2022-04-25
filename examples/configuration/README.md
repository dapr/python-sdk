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
timeout_seconds: 10
-->

```bash
docker exec dapr_redis redis-cli SET orderId "100||1"
docker exec dapr_redis redis-cli SET orderId1 "200||2"
```

<!-- END_STEP -->

## Run configuration example

Change directory to this folder:
```bash
cd examples/configuration 
```

To run this example, use the following command:

<!-- STEP
name: Run get configuration example
expected_stdout_lines:
  - "== APP == Got key=orderId value=100 version=1 metadata={}"
  - "== APP == Got key=orderId1 value=200 version=2 metadata={}"
  - "== APP == Subscribe key=orderId value=200 version=2 metadata={}"
background: true
sleep: 10
timeout_seconds: 50
-->

```bash
dapr run --app-id configexample --components-path components/ -- python3 configuration.py
```

```bash
docker exec dapr_redis redis-cli SET orderId "200||2"
```
<!-- END_STEP -->

You should be able to see the following output:
```
== APP == Got key=orderId value=100 version=1
== APP == Subscribe key=orderId value=200 version=2
```
