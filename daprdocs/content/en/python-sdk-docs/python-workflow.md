---
type: docs
title: "Getting started with the Dapr Workflow Python SDK"
linkTitle: "Workflow"
weight: 30000
description: How to get up and running with workflows using the Dapr Python SDK
---

Let’s create a Dapr workflow and invoke it using the console. In the [provided order processing workflow example](todo), the console prompts provide directions on how to both purchase and restock items. In this guide, you will:

- Create a Python console application using `DaprClient` ([workflow.py](https://github.com/dapr/python-sdk/examples/workflow))
- Utilize the Python workflow SDK and API calls to start and query workflow instances

This example uses the default configuration from `dapr init` in [self-hosted mode](https://github.com/dapr/cli#install-dapr-on-your-local-machine-self-hosted).

In the Python example project:
- The `workflow.py` file contains the setup of the app, including the registration of the workflow and workflow activities. 
- The workflow definition is found in the `todo` directory. 
- The workflow activity definitions are found in the `todo` directory.

## Prerequisites
- [Dapr CLI]({{< ref install-dapr-cli.md >}}) installed
- Initialized [Dapr environment]({{< ref install-dapr-selfhost.md >}})
- [Python 3.7+](https://www.python.org/downloads/) installed
- [Dapr Python module]({{< ref "python#install-the0dapr-module" >}}) installed
- Verify you're using the latest proto bindings

## Set up the environment

If it's not already installed, run the following command to install the requirements for running workflows with the Dapr Python SDK.

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

To run the Dapr application, you need to start the Python program and a Dapr sidecar. In the terminal, start the sidecar.

```bash
dapr run --app-id orderapp --app-protocol grpc --dapr-grpc-port 50001 --resources-path components --placement-host-address localhost:50005 -- python3 app.py
```

> **Note:** Since Python3.exe is not defined in Windows, you may need to use `python workflow.py` instead of `python3 workflow.py`.


## Start a workflow

To start a workflow, you have two options:

1. Follow the directions from the console prompts.
1. Use the workflow API and send a request to Dapr directly. 

This guide focuses on the workflow API option. 

{{% alert title="Note" color="primary" %}}
  - You can find the commands below in the `todo` file.
  - The body of the curl request is the purchase order information used as the input of the workflow. 
  - The "1234" in the commands represents the unique identifier for the workflow and can be replaced with any identifier of your choosing.
{{% /alert %}}

Run the following command to start a workflow. 

{{< tabs "Linux/MacOS" "Windows">}}

{{% codetab %}}

```bash
todo
```

{{% /codetab %}}

{{% codetab %}}

```powershell
todo
```

{{% /codetab %}}

{{< /tabs >}}

If successful, you should see a response like the following: 

```json
todo
```

Send an HTTP request to get the status of the workflow that was started:

```bash
todo
```

The workflow is designed to take several seconds to complete. If the workflow hasn't completed when you issue the HTTP request, you'll see the following JSON response (formatted for readability) with workflow status as `RUNNING`:

```json
todo
```

Once the workflow has completed running, you should see the following output, indicating that it has reached the `COMPLETED` status:

```json
todo
```

When the workflow has completed, the stdout of the workflow app should look like:

```log
todo
```


## Error Handling

The Dapr Python SDK will pass through errors that it receives from the Dapr runtime. In the case of an ETag mismatch, the Dapr runtime will return `StatusCode.ABORTED`.

**Example**

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

## Next steps
- [Learn more about Dapr workflow]({{< ref workflow-overview.md >}})
- [Workflow API reference]({{< ref workflow_api.md >}})