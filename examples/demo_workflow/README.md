# Example - Dapr Workflow Authoring

This document describes how to register a workflow and activities inside it and start running it.
It demonstrates the following APIs:
- **start_workflow**: Start an instance of a workflow
- **get_workflow**: Get information on a single workflow
- **terminate_workflow**: Terminate or stop a particular instance of a workflow
- **raise_event**: Raise an event on a workflow
- **pause_workflow**: Pauses or suspends a workflow instance that can later be resumed
- **resume_workflow**: Resumes a paused workflow instance
- **purge_workflow**: Removes all metadata related to a specific workflow instance from the state store
## Pre-requisites

- [Dapr CLI and initialized environment](https://docs.dapr.io/getting-started)
- [Install Python 3.10+](https://www.python.org/downloads/)

### Install requirements

You can install dapr SDK package using pip command:

```sh
pip3 install -r demo_workflow/requirements.txt
```

<!-- STEP
name: Running this example
expected_stdout_lines:
  - "Hi Counter!"
  - "New counter value is: 1!"
  - "New counter value is: 11!"
  - "Retry count value is: 0!"
  - "Retry count value is: 1! This print statement verifies retry"
  - "Appending 1 to child_orchestrator_string!"
  - "Appending a to child_orchestrator_string!"
  - "Appending a to child_orchestrator_string!"
  - "Appending 2 to child_orchestrator_string!"
  - "Appending b to child_orchestrator_string!"
  - "Appending b to child_orchestrator_string!"
  - "Appending 3 to child_orchestrator_string!"
  - "Appending c to child_orchestrator_string!"
  - "Appending c to child_orchestrator_string!"
  - "Get response from hello_world_wf after pause call: Suspended"
  - "Get response from hello_world_wf after resume call: Running"
  - "New counter value is: 111!"
  - "New counter value is: 1111!"
  - "Instance Successfully Purged"
  - "Get response from hello_world_wf after terminate call: Terminated"
  - "Get response from child_wf after terminate call: Terminated"
  - "Instance Successfully Purged"
background: true
timeout_seconds: 50
sleep: 15
-->

```sh
dapr run --app-id orderapp --app-protocol grpc --dapr-grpc-port 50001 --resources-path components --placement-host-address localhost:50005 -- python3 app.py
```

<!-- END_STEP -->

You should be able to see the following output:
```
Hi Counter!
New counter value is: 1!
New counter value is: 11!
Retry count value is: 0!
Retry count value is: 1! This print statement verifies retry
Appending 1 to child_orchestrator_string!
Appending a to child_orchestrator_string!
Appending a to child_orchestrator_string!
Appending 2 to child_orchestrator_string!
Appending b to child_orchestrator_string!
Appending b to child_orchestrator_string!
Appending 3 to child_orchestrator_string!
Appending c to child_orchestrator_string!
Appending c to child_orchestrator_string!
Get response from hello_world_wf after pause call: Suspended
Get response from hello_world_wf after resume call: Running
New counter value is: 111!
New counter value is: 1111!
Get response from hello_world_wf after terminate call: Terminated
Get response from child_wf after terminate call: Terminated
Instance Successfully Purged
```
