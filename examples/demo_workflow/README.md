# Example - Dapr Workflow Authoring

This document describes how to register a workflow and activities inside it and start running it.

## Pre-requisites

- [Dapr CLI and initialized environment](https://docs.dapr.io/getting-started)
- [Install Python 3.7+](https://www.python.org/downloads/)

### Install requirements

You can install dapr SDK package using pip command:

<!-- STEP
name: Install requirements
-->

```sh
pip3 install -r demo_workflow/requirements.txt
```

<!-- END_STEP -->

<!-- STEP
name: Running this example
expected_stdout_lines:
  - "== APP == New counter value is: 1!"
  - "== APP == New counter value is: 11!"
  - "== APP == New counter value is: 111!"
  - "== APP == New counter value is: 1111!"
background: true
timeout_seconds: 30
sleep: 15
-->

```sh
dapr run --app-id orderapp --app-protocol grpc --dapr-grpc-port 50001 --components-path components --placement-host-address localhost:50005 -- python3 app.py
```

<!-- END_STEP -->

You should be able to see the following output:
```
== APP == New counter value is: 1!
== APP == New counter value is: 11!
== APP == New counter value is: 111!
== APP == New counter value is: 1111!
```
