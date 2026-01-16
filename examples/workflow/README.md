# Workflow Examples

This directory contains examples of using the [Dapr Workflow](https://docs.dapr.io/developing-applications/building-blocks/workflow/) extension. You can find additional information about these examples in the [Dapr Workflow Application Patterns docs](https://docs.dapr.io/developing-applications/building-blocks/workflow/workflow-patterns#tabs-0-python).

## Prerequisites

- [Dapr CLI and initialized environment](https://docs.dapr.io/getting-started)
- [Install Python 3.9+](https://www.python.org/downloads/)

### Install requirements

You can install dapr SDK package using pip command:

```sh
pip3 install -r requirements.txt
```

## Running the samples

Each of the examples in this directory can be run directly from the command line.

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
  - "== APP == Hi Counter!"
  - "== APP == New counter value is: 1!"
  - "== APP == New counter value is: 11!"
  - "== APP == Retry count value is: 0!"
  - "== APP == Retry count value is: 1! This print statement verifies retry"
  - "== APP == Appending 1 to child_orchestrator_string!"
  - "== APP == Appending a to child_orchestrator_string!"
  - "== APP == Appending a to child_orchestrator_string!"
  - "== APP == Appending 2 to child_orchestrator_string!"
  - "== APP == Appending b to child_orchestrator_string!"
  - "== APP == Appending b to child_orchestrator_string!"
  - "== APP == Appending 3 to child_orchestrator_string!"
  - "== APP == Appending c to child_orchestrator_string!"
  - "== APP == Appending c to child_orchestrator_string!"
  - "== APP == Get response from hello_world_wf after pause call: SUSPENDED"
  - "== APP == Get response from hello_world_wf after resume call: RUNNING"
  - "== APP == New counter value is: 111!"
  - "== APP == New counter value is: 1111!"
  - "== APP == Workflow completed! Result: Completed"
timeout_seconds: 30
-->

```sh
dapr run --app-id wf-simple-example -- python3 simple.py
```
<!--END_STEP-->

The output of this example should look like this:

```
 - "== APP == Hi Counter!"
  - "== APP == New counter value is: 1!"
  - "== APP == New counter value is: 11!"
  - "== APP == Retry count value is: 0!"
  - "== APP == Retry count value is: 1! This print statement verifies retry"
  - "== APP == Appending 1 to child_orchestrator_string!"
  - "== APP == Appending a to child_orchestrator_string!"
  - "== APP == Appending a to child_orchestrator_string!"
  - "== APP == Appending 2 to child_orchestrator_string!"
  - "== APP == Appending b to child_orchestrator_string!"
  - "== APP == Appending b to child_orchestrator_string!"
  - "== APP == Appending 3 to child_orchestrator_string!"
  - "== APP == Appending c to child_orchestrator_string!"
  - "== APP == Appending c to child_orchestrator_string!"
  - "== APP == Get response from hello_world_wf after pause call: SUSPENDED"
  - "== APP == Get response from hello_world_wf after resume call: RUNNING"
  - "== APP == New counter value is: 111!"
  - "== APP == New counter value is: 1111!"
  - "== APP == Workflow completed! Result: Completed"
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
  - "== APP == Hi Counter!"
  - "== APP == New counter value is: 1!"
  - "== APP == New counter value is: 11!"
  - "== APP == Retry count value is: 0!"
  - "== APP == Retry count value is: 1! This print statement verifies retry"
  - "== APP == Appending 1 to child_orchestrator_string!"
  - "== APP == Appending a to child_orchestrator_string!"
  - "== APP == Appending a to child_orchestrator_string!"
  - "== APP == Appending 2 to child_orchestrator_string!"
  - "== APP == Appending b to child_orchestrator_string!"
  - "== APP == Appending b to child_orchestrator_string!"
  - "== APP == Appending 3 to child_orchestrator_string!"
  - "== APP == Appending c to child_orchestrator_string!"
  - "== APP == Appending c to child_orchestrator_string!"
  - "== APP == Get response from hello_world_wf after pause call: SUSPENDED"
  - "== APP == Get response from hello_world_wf after resume call: RUNNING"
  - "== APP == New counter value is: 111!"
  - "== APP == New counter value is: 1111!"
  - "== APP == Workflow completed! Result: Completed"
timeout_seconds: 30
-->

```sh
dapr run --app-id wf-simple-aio-example -- python3 simple_aio_client.py
```
<!--END_STEP-->

The output of this example should look like this:

```
 - "== APP == Hi Counter!"
  - "== APP == New counter value is: 1!"
  - "== APP == New counter value is: 11!"
  - "== APP == Retry count value is: 0!"
  - "== APP == Retry count value is: 1! This print statement verifies retry"
  - "== APP == Appending 1 to child_orchestrator_string!"
  - "== APP == Appending a to child_orchestrator_string!"
  - "== APP == Appending a to child_orchestrator_string!"
  - "== APP == Appending 2 to child_orchestrator_string!"
  - "== APP == Appending b to child_orchestrator_string!"
  - "== APP == Appending b to child_orchestrator_string!"
  - "== APP == Appending 3 to child_orchestrator_string!"
  - "== APP == Appending c to child_orchestrator_string!"
  - "== APP == Appending c to child_orchestrator_string!"
  - "== APP == Get response from hello_world_wf after pause call: SUSPENDED"
  - "== APP == Get response from hello_world_wf after resume call: RUNNING"
  - "== APP == New counter value is: 111!"
  - "== APP == New counter value is: 1111!"
  - "== APP == Workflow completed! Result: Completed"
```

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
dapr run --app-id wfexample -- python3 task_chaining.py
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
dapr run --app-id wfexample -- python3 fan_out_fan_in.py
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
dapr run --app-id wfexample
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
dapr run --app-id wfexample
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
dapr run --app-id wfexample
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


### Cross-app Workflow

This example demonstrates how to call child workflows and activities in different apps. The multiple Dapr CLI instances can be started using the following commands:

<!-- STEP
name: Run apps
expected_stdout_lines:
  - '== APP == app1 - triggering app1 workflow'
  - '== APP == app1 - received workflow call'
  - '== APP == app1 - triggering app2 workflow'
  - '== APP == app2 - received workflow call'
  - '== APP == app2 - triggering app3 activity'
  - '== APP == app3 - received activity call'
  - '== APP == app3 - returning activity result'
  - '== APP == app2 - received activity result'
  - '== APP == app2 - returning workflow result'
  - '== APP == app1 - received workflow result'
  - '== APP == app1 - returning workflow result'
background: true
sleep: 20
-->

```sh
dapr run --app-id wfexample3 python3 cross-app3.py &
dapr run --app-id wfexample2 python3 cross-app2.py &
dapr run --app-id wfexample1 python3 cross-app1.py
```
<!-- END_STEP -->

When you run the apps, you will see output like this:
```
...
app1 - triggering app2 workflow
app2 - triggering app3 activity
...
```
among others. This shows that the workflow calls are working as expected.


#### Error handling on activity calls

This example demonstrates how the error handling works on activity calls across apps.

Error handling on activity calls across apps works as normal workflow activity calls.

In this example we run `app3` in failing mode, which makes the activity call return error constantly. The activity call from `app2` will fail after the retry policy is exhausted.

<!-- STEP
name: Run apps
expected_stdout_lines:
  - '== APP == app1 - triggering app1 workflow'
  - '== APP == app1 - received workflow call'
  - '== APP == app1 - triggering app2 workflow'
  - '== APP == app2 - received workflow call'
  - '== APP == app2 - triggering app3 activity'
  - '== APP == app3 - received activity call'
  - '== APP == app3 - raising error in activity due to error mode being enabled'
  - '== APP == app2 - received activity error from app3'
  - '== APP == app2 - returning workflow result'
  - '== APP == app1 - received workflow result'
  - '== APP == app1 - returning workflow result'
sleep: 20
-->

```sh
export ERROR_ACTIVITY_MODE=true
dapr run --app-id wfexample3 python3 cross-app3.py &
dapr run --app-id wfexample2 python3 cross-app2.py &
dapr run --app-id wfexample1 python3 cross-app1.py
```
<!-- END_STEP -->


When you run the apps with the `ERROR_ACTIVITY_MODE` environment variable set, you will see output like this:
```
...
app3 - received activity call
app3 - raising error in activity due to error mode being enabled
app2 - received activity error from app3
...
```
among others. This shows that the activity calls are failing as expected, and they are being handled as expected too.


#### Error handling on workflow calls

This example demonstrates how the error handling works on workflow calls across apps.

Error handling on workflow calls across apps works as normal workflow calls.

In this example we run `app2` in failing mode, which makes the workflow call return error constantly. The workflow call from `app1` will fail after the retry policy is exhausted.

<!-- STEP
name: Run apps
expected_stdout_lines:
  - '== APP == app1 - triggering app1 workflow'
  - '== APP == app1 - received workflow call'
  - '== APP == app1 - triggering app2 workflow'
  - '== APP == app2 - received workflow call'
  - '== APP == app2 - raising error in workflow due to error mode being enabled'
  - '== APP == app1 - received workflow error from app2'
  - '== APP == app1 - returning workflow result'
sleep: 20
-->

```sh
export ERROR_WORKFLOW_MODE=true
dapr run --app-id wfexample3 python3 cross-app3.py &
dapr run --app-id wfexample2 python3 cross-app2.py &
dapr run --app-id wfexample1 python3 cross-app1.py
```
<!-- END_STEP -->

When you run the apps with the `ERROR_WORKFLOW_MODE` environment variable set, you will see output like this:
```
...
app2 - received workflow call
app2 - raising error in workflow due to error mode being enabled
app1 - received workflow error from app2
...
```
among others. This shows that the workflow calls are failing as expected, and they are being handled as expected too.


### Versioning

This example demonstrates how to version a workflow. The Dapr CLI can be started using the following command:

<!--STEP
name: Run the versioning example
match_order: none
expected_stdout_lines:
  - "== APP == test1: triggering workflow"
  - "== APP == test1: Received workflow call for version1"
  - "== APP == test1: Finished workflow for version1"
  - "== APP == test2: triggering workflow"
  - "== APP == test2: Received workflow call for version1"
  - "== APP == test2: Finished workflow for version1"
  - "== APP == test3: triggering workflow"
  - "== APP == test3: Received workflow call for version2"
  - "== APP == test3: Finished workflow for version2"
  - "== APP == test4: start"
  - "== APP == test4: patch1 is patched"
  - "== APP == test5: start"
  - "== APP == test5: patch1 is not patched"
  - "== APP == test5: patch2 is patched"
  - "== APP == test6: start"
  - "== APP == test6: patch1 is patched"
  - "== APP == test6: patch2 is patched"
  - "== APP == test7: Received workflow call for version1"
  - "== APP == test7: Workflow is stalled"
  - "== APP == test8: Workflow is stalled"
  - "== APP == test100: part2"
  - "== APP == test100: Received workflow call for version1"
  - "== APP == test100: Finished stalled version1 workflow"
  - "== APP == test100: Finished stalled patching workflow"
timeout_seconds: 60
-->

```sh
dapr run --app-id wf-versioning-example -- python3 versioning.py part1
dapr run --app-id wf-versioning-example -- python3 versioning.py part2
```
<!--END_STEP-->
