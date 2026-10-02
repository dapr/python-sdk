# Multi-app Workflows

## Prerequisites

Follow the [workflow prerequisites](../README.md#prerequisites), then run these commands from the repository root:

```sh
cd examples/workflow/multi-app
pip3 install -r ../requirements.txt
```

## Run the example

This example demonstrates how to call child workflows and activities in different apps. The multiple Dapr CLI instances can be started using the following commands:

<!-- STEP
name: Run apps
expected_stdout_lines:
  - 'app1 - triggering app1 workflow'
  - 'app1 - received workflow call'
  - 'app1 - triggering app2 workflow'
  - 'app2 - received workflow call'
  - 'app2 - triggering app3 activity'
  - 'app3 - received activity call'
  - 'app3 - returning activity result'
  - 'app2 - received activity result'
  - 'app2 - returning workflow result'
  - 'app1 - received workflow result'
  - 'app1 - returning workflow result'
background: true
sleep: 20
-->

```sh
dapr run --app-id wfexample3 -- python3 multi-app3.py &
dapr run --app-id wfexample2 -- python3 multi-app2.py &
dapr run --app-id wfexample1 -- python3 multi-app1.py
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

### Cross-app client operations

The multi-app examples above call across apps from inside a workflow. Client
operations can target another app too: pass `app_id` to
`schedule_new_workflow` and to the operations that follow, and each one is
applied to the instance owned by that app. The caller registers no workflow of
its own. Whether it is permitted is governed by the target app's
`WorkflowAccessPolicy`.

<!-- STEP
name: Run cross-app client
expected_stdout_lines:
  - 'client - scheduling a workflow on the host app'
  - 'host - workflow started'
  - 'client - remote workflow is RUNNING'
  - 'client - paused the remote workflow'
  - 'client - resumed the remote workflow'
  - 'client - remote workflow is COMPLETED'
  - 'client - purged the remote workflow'
background: true
sleep: 20
-->

```sh
dapr run --app-id wfcrossapphost -- python3 cross-app-client-host.py &
dapr run --app-id wfcrossappclient -- python3 cross-app-client.py
```
<!-- END_STEP -->

Requires a Dapr runtime with cross-app workflow support. Against an older
runtime the app ID is ignored and every operation applies to the caller's own
app.

### Error handling on activity calls

This example demonstrates how the error handling works on activity calls in multi-app workflows.

Error handling on activity calls in multi-app workflows works as normal workflow activity calls.

In this example we run `app3` in failing mode, which makes the activity call return error constantly. The activity call from `app2` will fail after the retry policy is exhausted.

<!-- STEP
name: Run apps
expected_stdout_lines:
  - 'app1 - triggering app1 workflow'
  - 'app1 - received workflow call'
  - 'app1 - triggering app2 workflow'
  - 'app2 - received workflow call'
  - 'app2 - triggering app3 activity'
  - 'app3 - received activity call'
  - 'app3 - raising error in activity due to error mode being enabled'
  - 'app2 - received activity error from app3'
  - 'app2 - returning workflow result'
  - 'app1 - received workflow result'
  - 'app1 - returning workflow result'
sleep: 20
-->

```sh
export ERROR_ACTIVITY_MODE=true
dapr run --app-id wfexample3 -- python3 multi-app3.py &
dapr run --app-id wfexample2 -- python3 multi-app2.py &
dapr run --app-id wfexample1 -- python3 multi-app1.py
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


### Error handling on workflow calls

This example demonstrates how the error handling works on workflow calls in multi-app workflows.

Error handling on workflow calls in multi-app workflows works as normal workflow calls.

In this example we run `app2` in failing mode, which makes the workflow call return error constantly. The workflow call from `app1` will fail after the retry policy is exhausted.

<!-- STEP
name: Run apps
expected_stdout_lines:
  - 'app1 - triggering app1 workflow'
  - 'app1 - received workflow call'
  - 'app1 - triggering app2 workflow'
  - 'app2 - received workflow call'
  - 'app2 - raising error in workflow due to error mode being enabled'
  - 'app1 - received workflow error from app2'
  - 'app1 - returning workflow result'
sleep: 20
-->

```sh
export ERROR_WORKFLOW_MODE=true
dapr run --app-id wfexample3 -- python3 multi-app3.py &
dapr run --app-id wfexample2 -- python3 multi-app2.py &
dapr run --app-id wfexample1 -- python3 multi-app1.py
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
