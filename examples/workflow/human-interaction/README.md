# Human Interaction

## Prerequisites

Follow the [workflow prerequisites](../README.md#prerequisites), then run these commands from the repository root:

```sh
cd examples/workflow/human-interaction
pip3 install -r ../requirements.txt
```

## Run the example

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
