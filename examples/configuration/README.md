# Example - Get Configuration

This example demonstrates the Configuration APIs in Dapr.
It demonstrates the following APIs:
- **configuration**: Get configuration from statestore

> **Note:** Make sure to use the latest proto bindings

## Pre-requisites

- [Dapr CLI and initialized environment](https://docs.dapr.io/getting-started)
- [Install Python 3.10+](https://www.python.org/downloads/)

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
sleep: 3
-->

```bash
docker exec dapr_redis redis-cli SET orderId1 "100||1"
docker exec dapr_redis redis-cli SET orderId2 "200||1"
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
match_order: none
expected_stdout_lines:
  - "Got key=orderId1 value=100 version=1 metadata={}"
  - "Got key=orderId2 value=200 version=1 metadata={}"
  - "Subscribe key=orderId2 value=210 version=2 metadata={}"
  - "Unsubscribed successfully? True"
background: true
timeout_seconds: 30
sleep: 3
-->

```bash
dapr run --app-id configexample --resources-path components/ -- python3 configuration.py
```
<!-- END_STEP -->

<!-- STEP
name: Set configuration value
expected_stdout_lines:
  - "OK"
timeout_seconds: 5
-->

```bash
docker exec dapr_redis redis-cli SET orderId2 "210||2"
```
<!-- END_STEP -->

You should be able to see the following output:
```
Got key=orderId1 value=100 version=1
Got key=orderId2 value=200 version=1
Subscribe key=orderId2 value=210 version=2
```
