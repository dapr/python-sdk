# Example - Get Configuration

This example demonstrates the State Store Query Alpha API in Dapr.
It demonstrates the following APIs:
- **querystatealpha1**: Queries a compatible Dapr state store

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
timeout_seconds: 120
-->

```bash
docker run -d --rm -p 27017:27017 --name mongodb mongo:5
```

<!-- END_STEP -->

## Run the example

Change directory to this folder:
```bash
cd examples/state_store_query
```

To run this example, start by importing the test data

<!-- STEP
name: Import test data
timeout_seconds: 10
-->

```bash
# Import the example dataset
dapr run --app-id demo --dapr-http-port 3500 --components-path components -- curl -X POST -H "Content-Type: application/json" -d @dataset.json http://localhost:3500/v1.0/state/statestore
```
<!-- END_STEP -->


Now run the app

<!-- STEP
name: Run get query example
expected_stdout_lines:
- '== APP == 1 {"city": "Seattle", "person": {"id": {"$numberDouble": "1036.0"}, "org": "Dev Ops"}, "state": "WA"}'
- '== APP == 4 {"city": "Spokane", "person": {"id": {"$numberDouble": "1042.0"}, "org": "Dev Ops"}, "state": "WA"}'
- '== APP == 10 {"city": "New York", "person": {"id": {"$numberDouble": "1054.0"}, "org": "Dev Ops"}, "state": "NY"}'
- '== APP == Token: 3'
- '== APP == 9 {"city": "San Diego", "person": {"id": {"$numberDouble": "1002.0"}, "org": "Finance"}, "state": "CA"}'
- '== APP == 7 {"city": "San Francisco", "person": {"id": {"$numberDouble": "1015.0"}, "org": "Dev Ops"}, "state": "CA"}'
- '== APP == 3 {"city": "Sacramento", "person": {"id": {"$numberDouble": "1071.0"}, "org": "Finance"}, "state": "CA"}'
- '== APP == Token: 6'
timeout_seconds: 5
-->

```bash
dapr run --app-id queryexample --components-path components/ -- python3 state_store_query.py
```
<!-- END_STEP -->

You should be able to see the following output:
```
== APP == 1 {"city": "Seattle", "person": {"id": {"$numberDouble": "1036.0"}, "org": "Dev Ops"}, "state": "WA"}
== APP == 4 {"city": "Spokane", "person": {"id": {"$numberDouble": "1042.0"}, "org": "Dev Ops"}, "state": "WA"}
== APP == 10 {"city": "New York", "person": {"id": {"$numberDouble": "1054.0"}, "org": "Dev Ops"}, "state": "NY"}
== APP == Token: 3
== APP == 9 {"city": "San Diego", "person": {"id": {"$numberDouble": "1002.0"}, "org": "Finance"}, "state": "CA"}
== APP == 7 {"city": "San Francisco", "person": {"id": {"$numberDouble": "1015.0"}, "org": "Dev Ops"}, "state": "CA"}
== APP == 3 {"city": "Sacramento", "person": {"id": {"$numberDouble": "1071.0"}, "org": "Finance"}, "state": "CA"}
== APP == Token: 6
```

Cleanup

<!-- STEP
name: Cleanup
expected_stdout_lines:
- "mongodb"
timeout_seconds: 5
-->

```bash
docker kill mongodb
```

<!-- END_STEP -->