# Monitor

## Prerequisites

Follow the [workflow prerequisites](../README.md#prerequisites), then run these commands from the repository root:

```sh
cd examples/workflow/monitor
pip3 install -r ../requirements.txt
```

## Run the example

This example demonstrates how to run an eternal workflow that polls an endpoint to detect service health events. This example requires input from the user, so you'll need to have a separate command for the Dapr CLI and the Python app.

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
