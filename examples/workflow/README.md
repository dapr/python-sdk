# Workflow Examples

This directory contains examples of using the [Dapr Workflow](https://docs.dapr.io/developing-applications/building-blocks/workflow/) extension. You can find additional information about these examples in the [Dapr Workflow Application Patterns docs](https://docs.dapr.io/developing-applications/building-blocks/workflow/workflow-patterns#tabs-0-python).

## Prerequisites

- [Dapr CLI and initialized environment](https://docs.dapr.io/getting-started)
- [Install Python 3.10+](https://www.python.org/downloads/)

### Install requirements

You can install dapr SDK package using pip command:

```sh
pip3 install -r requirements.txt
```

## Running the samples

Run the standalone examples below from `examples/workflow`. For a [workflow pattern](#workflow-patterns), change into its directory and follow its README.

### Simple Workflow
This example represents a workflow that manages counters through a series of activities and child workflows.
It shows several Dapr Workflow features including:
- Basic activity execution with counter increments
- Retryable activities with configurable retry policies
- Child workflow orchestration with retry logic
- External event handling with timeouts
- Workflow state management (pause/resume)
- Activity error handling and retry backoff
- Global state tracking across workflow components
- Workflow lifecycle management (start, pause, resume, purge)

<!--STEP
name: Run the simple workflow example
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
  - "Get response from hello_world_wf after pause call: SUSPENDED"
  - "Get response from hello_world_wf after resume call: RUNNING"
  - "New counter value is: 111!"
  - "New counter value is: 1111!"
  - "Workflow completed! Result: Completed"
timeout_seconds: 30
-->

```sh
dapr run --app-id wf-simple-example -- python3 simple.py
```
<!--END_STEP-->

The output of this example should look like this:

```
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
  - "Get response from hello_world_wf after pause call: SUSPENDED"
  - "Get response from hello_world_wf after resume call: RUNNING"
  - "New counter value is: 111!"
  - "New counter value is: 1111!"
  - "Workflow completed! Result: Completed"
```

### Simple Workflow with async workflow client
This example represents a workflow that manages counters through a series of activities and child workflows. It features using the async workflow client.
It shows several Dapr Workflow features including:
- Basic activity execution with counter increments
- Retryable activities with configurable retry policies
- Child workflow orchestration with retry logic
- External event handling with timeouts
- Workflow state management (pause/resume)
- Activity error handling and retry backoff
- Global state tracking across workflow components
- Workflow lifecycle management (start, pause, resume, purge)

<!--STEP
name: Run the simple workflow example
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
  - "Get response from hello_world_wf after pause call: SUSPENDED"
  - "Get response from hello_world_wf after resume call: RUNNING"
  - "New counter value is: 111!"
  - "New counter value is: 1111!"
  - "Workflow completed! Result: Completed"
timeout_seconds: 30
-->

```sh
dapr run --app-id wf-simple-aio-example -- python3 simple_aio_client.py
```
<!--END_STEP-->

The output of this example should look like this:

```
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
  - "Get response from hello_world_wf after pause call: SUSPENDED"
  - "Get response from hello_world_wf after resume call: RUNNING"
  - "New counter value is: 111!"
  - "New counter value is: 1111!"
  - "Workflow completed! Result: Completed"
```

### Workflow patterns

Each workflow pattern has its own directory and README with setup instructions, run commands, and expected output.

| Pattern | Example directory |
|---------|-------------------|
| Task Chaining | [task-chaining](task-chaining/README.md) |
| Fan-out/Fan-in | [fan-out-fan-in](fan-out-fan-in/README.md) |
| Human Interaction | [human-interaction](human-interaction/README.md) |
| Monitor | [monitor](monitor/README.md) |
| Child Workflow | [child-workflow](child-workflow/README.md) |
| Multi-app Workflows | [multi-app](multi-app/README.md) |

### Versioning

This example demonstrates how to version a workflow.
The test consists of two parts:
1. Uses most of the common features of the workflow versioning. It also leaves some workflows stalled to demonstrate the stalled workflow feature.
2. Fixes the stalled workflows to get them to completion.

It had to be done in two parts because the runtime needs to be restarted in order to rerun stalled workflows.

 The Dapr CLI can be started using the following command:

<!--STEP
name: Run the versioning example
match_order: none
expected_stdout_lines:
  - "test1: triggering workflow"
  - "test1: Received workflow call for version1"
  - "test1: Finished workflow for version1"
  - "test2: triggering workflow"
  - "test2: Received workflow call for version1"
  - "test2: Finished workflow for version1"
  - "test3: triggering workflow"
  - "test3: Received workflow call for version2"
  - "test3: Finished workflow for version2"
  - "test4: start"
  - "test4: patch1 is patched"
  - "test5: start"
  - "test5: patch1 is not patched"
  - "test5: patch2 is patched"
  - "test6: start"
  - "test6: patch1 is patched"
  - "test6: patch2 is patched"
  - "test7: Received workflow call for version1"
  - "test7: Workflow is stalled"
  - "test8: Workflow is stalled"
  - "test100: part2"
  - "test100: Finished stalled version1 workflow"
  - "test100: Finished stalled patching workflow"
timeout_seconds: 60
-->

```sh
dapr run --app-id wf-versioning-example -- python3 versioning.py part1
dapr run --app-id wf-versioning-example --log-level debug -- python3 versioning.py part2
```
<!--END_STEP-->

### Pydantic models as workflow/activity inputs

This example shows how to pass [Pydantic](https://docs.pydantic.dev/) `BaseModel`
instances directly as workflow and activity inputs. When a workflow or activity
annotates its input parameter with a `BaseModel` subclass, the runtime
reconstructs the model from the decoded JSON payload automatically — no manual
`model_validate` call is needed at the receiving side.

The wire format remains plain JSON, so workflows and activities stay
interop-friendly with non-Python Dapr apps. Outputs coming back from activities
arrive as dicts; reconstructing them into a typed instance is a one-liner
(`OrderResult.model_validate(...)`).

<!--STEP
name: Run the pydantic models example
expected_stdout_lines:
  - "[workflow] received order O-100 for Acme amount=42.0"
  - "[activity] approving order O-100"
  - "[workflow] activity returned approved=True"
  - "[client] workflow output: order_id=O-100 approved=True message=auto-approved"
timeout_seconds: 60
-->

```sh
dapr run --app-id wf-pydantic-example -- python3 pydantic_models.py
```
<!--END_STEP-->

### History Propagation

This example demonstrates how a parent workflow can propagate its execution
history to a child workflow and to an activity, and how the receivers query
that history through `ctx.get_propagated_history()`.

It shows:
- `propagation=PropagationScope.OWN_HISTORY` on a child workflow call —
  forwards the caller's events only.
- `propagation=PropagationScope.LINEAGE` on an activity call — forwards the
  caller's events *plus* anything the caller itself received from its parent.
- `PropagatedHistory.get_last_workflow_by_name(...)` and
  `WorkflowResult.get_last_activity_by_name(...)` on the receiving side.

> **Requires** a Dapr sidecar with workflow history propagation support
> (durabletask-go PR #85 / runtime 1.18+ ). With an older sidecar the
> propagation field is silently dropped and `get_propagated_history()`
> returns `None`.

```sh
dapr run --app-id workflow-history-propagation -- python3 history_propagation.py
```

### Async Activities

This example fans out several `async def` activities, then aggregates their
results in a sync activity. Each async activity awaits a delay to stand in for
an I/O call, so the instances run concurrently on the worker's event loop
instead of taking a thread each.

Fan-out width and payload sizes are set with environment variables:
`WORKFLOW_FAN_OUT` (default 5), `WORKFLOW_INPUT_BYTES` (default 2048),
`WORKFLOW_OUTPUT_BYTES` (default 1024), and `WORKFLOW_IO_SECONDS` (default 1.0).

See [concurrency.md](../../dapr/ext/workflow/docs/concurrency.md) for when to
prefer async over sync activities and how to size the concurrency knobs.

```sh
dapr run --app-id workflow-async-activities -- python3 async_activities.py
```

The output should look like this (the async lines can arrive in any order):

```
Workflow started. Instance ID: 7b3e9c1f...
[async] payload 0: 2048B in -> 1024B out
[async] payload 1: 2048B in -> 1024B out
[async] payload 2: 2048B in -> 1024B out
[async] payload 3: 2048B in -> 1024B out
[async] payload 4: 2048B in -> 1024B out
[sync] 5 results, 5120 bytes
Workflow completed! Status: COMPLETED
Workflow result: 5 results, 5120 bytes
```
