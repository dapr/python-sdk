# Workflow Examples

This directory contains examples of using the [Dapr Workflow](https://docs.dapr.io/developing-applications/building-blocks/workflow/) extension. You can find additional information about these examples in the [Dapr Workflow Application Patterns docs](https://docs.dapr.io/developing-applications/building-blocks/workflow/workflow-patterns#tabs-0-python).

## Prerequisites

- [Dapr CLI and initialized environment](https://docs.dapr.io/getting-started)
- [Install Python 3.8+](https://www.python.org/downloads/)

### Install requirements

You can install dapr SDK package using pip command:

```sh
pip3 install -r requirements.txt
```

## Running the samples

Each of the examples in this directory can be run directly from the command line.

### Task Chaining

This example demonstrates how to chain "activity" tasks together in a workflow. You can run this sample using the following command:
<!--STEP
name: Run the task chaining example
expected_stdout_lines:
  - "== APP == Step 1: Received input: 42."
  - "== APP == Step 2: Received input: 43."
  - "== APP == Step 3: Received input: 86."
  - "== APP == Workflow completed! Status: WorkflowStatus.COMPLETED"
timeout_seconds: 30
-->

```sh
dapr run --app-id wfexample --dapr-grpc-port 50001 -- python3 task_chaining.py
```
<!--END_STEP-->

The output of this example should look like this:

```
== APP == Workflow started. Instance ID: b716208586c24829806b44b62816b598
== APP == Step 1: Received input: 42.
== APP == Step 2: Received input: 43.
== APP == Step 3: Received input: 86.
== APP == Workflow completed! Status: WorkflowStatus.COMPLETED
```

### Fan-out/Fan-in

This example demonstrates how to fan-out a workflow into multiple parallel tasks, and then fan-in the results of those tasks. You can run this sample using the following command:

<!--STEP
name: Run the fan-out/fan-in example
match_order: none
expected_stdout_lines:
  - "== APP == Processing work item: 1."
  - "== APP == Processing work item: 2."
  - "== APP == Processing work item: 3."
  - "== APP == Processing work item: 4."
  - "== APP == Processing work item: 5."
  - "== APP == Processing work item: 6."
  - "== APP == Processing work item: 7."
  - "== APP == Processing work item: 8."
  - "== APP == Processing work item: 9."
  - "== APP == Processing work item: 10."
  - "== APP == Work item 1 processed. Result: 2."
  - "== APP == Work item 2 processed. Result: 4."
  - "== APP == Work item 3 processed. Result: 6."
  - "== APP == Work item 4 processed. Result: 8."
  - "== APP == Work item 5 processed. Result: 10."
  - "== APP == Work item 6 processed. Result: 12."
  - "== APP == Work item 7 processed. Result: 14."
  - "== APP == Work item 8 processed. Result: 16."
  - "== APP == Work item 9 processed. Result: 18."
  - "== APP == Work item 10 processed. Result: 20."
  - "== APP == Final result: 110."
timeout_seconds: 30
-->

```sh
dapr run --app-id wfexample --dapr-grpc-port 50001 -- python3 fan_out_fan_in.py
```
<!--END_STEP-->

The output of this sample should look like this:

```
== APP == Workflow started. Instance ID: 2e656befbb304e758776e30642b75944
== APP == Processing work item: 1.
== APP == Processing work item: 2.
== APP == Processing work item: 3.
== APP == Processing work item: 4.
== APP == Processing work item: 5.
== APP == Processing work item: 6.
== APP == Processing work item: 7.
== APP == Processing work item: 8.
== APP == Processing work item: 9.
== APP == Processing work item: 10.
== APP == Work item 1 processed. Result: 2.
== APP == Work item 2 processed. Result: 4.
== APP == Work item 3 processed. Result: 6.
== APP == Work item 4 processed. Result: 8.
== APP == Work item 5 processed. Result: 10.
== APP == Work item 6 processed. Result: 12.
== APP == Work item 7 processed. Result: 14.
== APP == Work item 8 processed. Result: 16.
== APP == Work item 9 processed. Result: 18.
== APP == Work item 10 processed. Result: 20.
== APP == Final result: 110.
```

Note that the ordering of the work-items is non-deterministic since they are all running in parallel.

### Human Interaction

This example demonstrates how to use a workflow to interact with a human user. This example requires input from the user, so you'll need to have a separate command for the Dapr CLI and the Python app.

The Dapr CLI can be started using the following command:

```sh
dapr run --app-id wfexample --dapr-grpc-port 50001
```

In a separate terminal window, run the following command to start the Python workflow app:

```sh
 python3 human_approval.py
 ```

When you run the example, you will see output as well as a prompt like this:

```
*** Requesting approval from user for order: namespace(cost=2000, product='MyProduct', quantity=1)
Press [ENTER] to approve the order...
```

Press the `ENTER` key to continue the workflow. If `ENTER` is pressed before the hardcoded timeout expires, then the following output will be displayed:

```
*** Placing order: namespace(cost=2000, product='MyProduct', quantity=1)
Workflow completed! Result: "Approved by 'Me'"
```

However, if the timeout expires before `ENTER` is pressed, then the following output will be displayed:

```
*** Workflow timed out!
```

### Monitor

This example demonstrates how to eternally running workflow that polls an endpoint to detect service health events. This example requires input from the user, so you'll need to have a separate command for the Dapr CLI and the Python app.

The Dapr CLI can be started using the following command:

```sh
dapr run --app-id wfexample --dapr-grpc-port 50001
```

In a separate terminal window, run the following command to start the Python workflow app:

```sh
python3 monitor.py
```

The workflow runs forever, or until the app is stopped. While it is running, it will periodically report information about whether a "job" is healthy or unhealthy. After several minutes, the output of this workflow will look something like this (note that the healthy and unhealthy message ordering is completely random):

```
Press Enter to stop...
Job 'job1' is healthy.
Job 'job1' is healthy.
Job 'job1' is unhealthy.
*** Alert: Job 'job1' is unhealthy!
Job 'job1' is healthy.
Job 'job1' is healthy.
Job 'job1' is healthy.
Job 'job1' is unhealthy.
*** Alert: Job 'job1' is unhealthy!
Job 'job1' is unhealthy.
```

This workflow runs forever or until you press `ENTER` to stop it. Starting the app again after stopping it will cause the same workflow instance to resume where it left off.

### Child Workflow

This example demonstrates how to call a child workflow. The Dapr CLI can be started using the following command:

```sh
dapr run --app-id wfexample --dapr-grpc-port 50001
```

In a separate terminal window, run the following command to start the Python workflow app:

```sh
python3 child_workflow.py
```

When you run the example, you will see output like this:
```
...
*** Calling child workflow 29a7592a1e874b07aad2bb58de309a51-child
*** Child workflow 6feadc5370184b4998e50875b20084f6 called
...
```