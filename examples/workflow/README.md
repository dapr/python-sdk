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
  - "== APP == Attempting to start OrderProcessingWorkflow"
  - "== APP == Get response from OrderProcessingWorkflow after start call: RUNNING"
  - "== APP == Get response from OrderProcessingWorkflow after pause call: SUSPENDED"
  - "== APP == Get response from OrderProcessingWorkflow after resume call: RUNNING"
  - "== APP == Get response from OrderProcessingWorkflow after terminate call: TERMINATED"
timeout_seconds: 5
-->

```bash
dapr run -- python3 workflow.py
```
<!-- END_STEP -->

The output should be as follows:

```
== APP == Get response from OrderProcessingWorkflow after start call: RUNNING

== APP == Get response from OrderProcessingWorkflow after pause call: SUSPENDED

== APP == Get response from OrderProcessingWorkflow after resume call: RUNNING

== APP == Get response from OrderProcessingWorkflow after terminate call: TERMINATED

```

