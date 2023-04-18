# Example - workflow

This example demonstrates the workflow APIs in Dapr.
It demonstrates the following APIs:
- **start_workflow**: Start an instance of a workflow
- **get_workflow**: Get information on a single workflow
- **terminate_workflow**: Terminate or stop a particular instance of a workflow
- **raise_event**: Raise an event on a workflow
- **pause_workflow**: Pauses or suspends a workflow instance that can later be resumed
- **resume_workflow**: Resumes a paused workflow instance
- **purge_workflow**: Removes all metadata related to a specific workflow instance

It creates a client using `DaprClient` and calls all the state API methods available as example.
It uses the default configuration from Dapr init in [self-hosted mode](https://github.com/dapr/cli#install-dapr-on-your-local-machine-self-hosted). 

> **Note:** Make sure to use the latest proto bindings

## Pre-requisites

- [Dapr CLI and initialized environment](https://docs.dapr.io/getting-started)
- [Install Python 3.7+](https://www.python.org/downloads/)

## Install Dapr python-SDK

<!-- Our CI/CD pipeline automatically installs the correct version, so we can skip this step in the automation -->

```bash
pip3 install dapr
```

## Run the example TODO: RRL FIX ALL THIS BELOW

To run this example, the following code can be utilized:

<!-- STEP
name: Run state store example
expected_stdout_lines:
  - "== APP == State store has successfully saved value_1 with key_1 as key"
  - "== APP == Cannot save due to bad etag. ErrorCode=StatusCode.ABORTED"
  - "== APP == State store has successfully saved value_2 with key_2 as key"
  - "== APP == State store has successfully saved value_3 with key_3 as key"
  - "== APP == Cannot save bulk due to bad etags. ErrorCode=StatusCode.ABORTED"
  - "== APP == Got value=b'value_1' eTag=1"
  - "== APP == Got items with etags: [(b'value_1_updated', '2'), (b'value_2', '2')]"
  - "== APP == Got value after delete: b''"
timeout_seconds: 5
-->

```bash
dapr run -- python3 workflow.py
```
<!-- END_STEP -->

The output should be as follows:

```
== APP == State store has successfully saved value_1 with key_1 as key

== APP == Cannot save due to bad etag. ErrorCode=StatusCode.ABORTED

== APP == State store has successfully saved value_2 with key_2 as key

== APP == State store has successfully saved value_3 with key_3 as key

== APP == Cannot save bulk due to bad etags. ErrorCode=StatusCode.ABORTED

== APP == Got value=b'value_1' eTag=1

== APP == Got items with etags: [(b'value_1_updated', '2'), (b'value_2', '2')]

== APP == Got value after delete: b''
```

## Error Handling

The Dapr python-sdk will pass through errors that it receives from the Dapr runtime. In the case of an etag mismatch, the Dapr runtime will return StatusCode.ABORTED
