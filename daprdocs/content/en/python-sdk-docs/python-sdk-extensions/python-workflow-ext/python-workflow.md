---
type: docs
title: "Getting started with the Dapr Workflow Python SDK"
linkTitle: "Workflow"
weight: 30000
description: How to get up and running with workflows using the Dapr Python SDK
---

{{% alert title="Note" color="primary" %}}
Dapr Workflow is currently in alpha.
{{% /alert %}}

Let’s create a Dapr workflow and invoke it using the console. With the [provided hello world workflow example](https://github.com/dapr/python-sdk/tree/master/examples/demo_workflow), you will:

- Run a [Python console application using `DaprClient`](https://github.com/dapr/python-sdk/blob/master/examples/demo_workflow/app.py)
- Utilize the Python workflow SDK and API calls to start, pause, resume, terminate, and purge workflow instances

This example uses the default configuration from `dapr init` in [self-hosted mode](https://github.com/dapr/cli#install-dapr-on-your-local-machine-self-hosted).

In the Python example project, the `app.py` file contains the setup of the app, including:
- The workflow definition 
- The workflow activity definitions
- The registration of the workflow and workflow activities 

## Prerequisites
- [Dapr CLI]({{< ref install-dapr-cli.md >}}) installed
- Initialized [Dapr environment]({{< ref install-dapr-selfhost.md >}})
- [Python 3.7+](https://www.python.org/downloads/) installed
- [Dapr Python package]({{< ref "python#installation" >}}) and the [workflow extension]({{< ref "python-workflow/_index.md" >}}) installed
- Verify you're using the latest proto bindings

## Set up the environment

Run the following command to install the requirements for running this workflow sample with the Dapr Python SDK.

```bash
pip3 install -r demo_workflow/requirements.txt
```

Clone the [Python SDK repo].

```bash
git clone https://github.com/dapr/python-sdk.git
```

From the Python SDK root directory, navigate to the Dapr Workflow example.

```bash
cd examples/demo_workflow
```

## Run the application locally

To run the Dapr application, you need to start the Python program and a Dapr sidecar. In the terminal, run:

```bash
dapr run --app-id orderapp --app-protocol grpc --dapr-grpc-port 50001 --resources-path components --placement-host-address localhost:50005 -- python3 app.py
```

> **Note:** Since Python3.exe is not defined in Windows, you may need to use `python app.py` instead of `python3 app.py`.


**Expected output**

```
== APP == ==========Start Counter Increase as per Input:==========

== APP == start_resp exampleInstanceID

== APP == Hi Counter!
== APP == New counter value is: 1!

== APP == Hi Counter!
== APP == New counter value is: 11!

== APP == Hi Counter!
== APP == Hi Counter!
== APP == Get response from hello_world_wf after pause call: Suspended

== APP == Hi Counter!
== APP == Get response from hello_world_wf after resume call: Running

== APP == Hi Counter!
== APP == New counter value is: 111!

== APP == Hi Counter!
== APP == Instance Successfully Purged

== APP == start_resp exampleInstanceID

== APP == Hi Counter!
== APP == New counter value is: 1112!

== APP == Hi Counter!
== APP == New counter value is: 1122!

== APP == Get response from hello_world_wf after terminate call: Terminated
== APP == Instance Successfully Purged
```

## What happened?

When you ran `dapr run`, the Dapr client:
1. Registered the workflow (`hello_world_wf`) and its actvity (`hello_act`)
1. Started the workflow engine

```python
def main():
    with DaprClient() as d:
        host = settings.DAPR_RUNTIME_HOST
        port = settings.DAPR_GRPC_PORT
        workflowRuntime = WorkflowRuntime(host, port)
        workflowRuntime = WorkflowRuntime()
        workflowRuntime.register_workflow(hello_world_wf)
        workflowRuntime.register_activity(hello_act)
        workflowRuntime.start()

        print("==========Start Counter Increase as per Input:==========")
        start_resp = d.start_workflow(instance_id=instanceId, workflow_component=workflowComponent,
                        workflow_name=workflowName, input=inputData, workflow_options=workflowOptions)
        print(f"start_resp {start_resp.instance_id}")
```

Dapr then paused and resumed the workflow:

```python
       # Pause
        d.pause_workflow(instance_id=instanceId, workflow_component=workflowComponent)
        getResponse = d.get_workflow(instance_id=instanceId, workflow_component=workflowComponent)
        print(f"Get response from {workflowName} after pause call: {getResponse.runtime_status}")

        # Resume
        d.resume_workflow(instance_id=instanceId, workflow_component=workflowComponent)
        getResponse = d.get_workflow(instance_id=instanceId, workflow_component=workflowComponent)
        print(f"Get response from {workflowName} after resume call: {getResponse.runtime_status}")
```

Once the workflow resumed, Dapr raised a workflow event and printed the new counter value:

```python
        # Raise event
        d.raise_workflow_event(instance_id=instanceId, workflow_component=workflowComponent,
                    event_name=eventName, event_data=eventData)
```

To clear out the workflow state from your state store, Dapr purged the workflow:

```python
        # Purge
        d.purge_workflow(instance_id=instanceId, workflow_component=workflowComponent)
        try:
            getResponse = d.get_workflow(instance_id=instanceId, workflow_component=workflowComponent)
        except DaprInternalError as err:
            if nonExistentIDError in err._message:
                print("Instance Successfully Purged")
```

The sample then demonstrated terminating a workflow by:
- Starting a new workflow using the same `instanceId` as the purged workflow.
- Terminating the workflow and purging before shutting down the workflow.

```python
        # Kick off another workflow
        start_resp = d.start_workflow(instance_id=instanceId, workflow_component=workflowComponent,
                        workflow_name=workflowName, input=inputData, workflow_options=workflowOptions)
        print(f"start_resp {start_resp.instance_id}")

        # Terminate
        d.terminate_workflow(instance_id=instanceId, workflow_component=workflowComponent)
        sleep(1)
        getResponse = d.get_workflow(instance_id=instanceId, workflow_component=workflowComponent)
        print(f"Get response from {workflowName} after terminate call: {getResponse.runtime_status}")

        # Purge
        d.purge_workflow(instance_id=instanceId, workflow_component=workflowComponent)
        try:
            getResponse = d.get_workflow(instance_id=instanceId, workflow_component=workflowComponent)
        except DaprInternalError as err:
            if nonExistentIDError in err._message:
                print("Instance Successfully Purged")
```

## Next steps
- [Learn more about Dapr workflow]({{< ref workflow >}})
- [Workflow API reference]({{< ref workflow_api.md >}})
