# Task Chaining

## Prerequisites

Follow the [workflow prerequisites](../README.md#prerequisites), then run these commands from the repository root:

```sh
cd examples/workflow/task-chaining
pip3 install -r ../requirements.txt
```

## Run the example

This example demonstrates how to chain "activity" tasks together in a workflow. You can run this sample using the following command:
<!--STEP
name: Run the task chaining example
expected_stdout_lines:
  - "Step 1: Received input: 42."
  - "Step 2: Received input: 43."
  - "Step 3: Received input: 86."
  - "Workflow completed! Status: WorkflowStatus.COMPLETED"
timeout_seconds: 30
-->

```sh
dapr run --app-id wfexample -- python3 task_chaining.py
```
<!--END_STEP-->

The output of this example should look like this:

```
Workflow started. Instance ID: b716208586c24829806b44b62816b598
Step 1: Received input: 42.
Step 2: Received input: 43.
Step 3: Received input: 86.
Workflow completed! Status: WorkflowStatus.COMPLETED
```
