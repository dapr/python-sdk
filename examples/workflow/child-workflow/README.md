# Child Workflow

## Prerequisites

Follow the [workflow prerequisites](../README.md#prerequisites), then run these commands from the repository root:

```sh
cd examples/workflow/child-workflow
pip3 install -r ../requirements.txt
```

## Run the example

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
