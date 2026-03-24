# Durable Task Client SDK for Python (Dapr fork)

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](https://opensource.org/licenses/MIT)
[![Build Validation](https://github.com/microsoft/durabletask-python/actions/workflows/pr-validation.yml/badge.svg)](https://github.com/microsoft/durabletask-python/actions/workflows/pr-validation.yml)
[![PyPI version](https://badge.fury.io/py/durabletask.svg)](https://badge.fury.io/py/durabletask)

This repo contains a Python client SDK for use with the [Durable Task Framework for Go](https://github.com/microsoft/durabletask-go) and [Dapr Workflow](https://docs.dapr.io/developing-applications/building-blocks/workflow/workflow-overview/). With this SDK, you can define, schedule, and manage durable orchestrations using ordinary Python code.

⚠️ **This SDK is currently under active development and is not yet ready for production use.** ⚠️

> Note that this project is **not** currently affiliated with the [Durable Functions](https://docs.microsoft.com/azure/azure-functions/durable/durable-functions-overview) project for Azure Functions. If you are looking for a Python SDK for Durable Functions, please see [this repo](https://github.com/Azure/azure-functions-durable-python).


## Minimal worker setup

To execute orchestrations and activities you must run a worker that connects to the Dapr Workflow sidecar and dispatches work on background threads:

```python
from durabletask.worker import TaskHubGrpcWorker

worker = TaskHubGrpcWorker(host_address="localhost:4001")

worker.add_orchestrator(say_hello)
worker.add_activity(hello_activity)

try:
    worker.start()
    # Worker runs in the background and processes work until stopped
finally:
    worker.stop()
```

Always stop the worker when you're finished. The worker keeps polling threads alive; if you skip `stop()` they continue running and can prevent your process from shutting down cleanly after failures. You can rely on the context manager form to guarantee cleanup:

```python
from durabletask.worker import TaskHubGrpcWorker

with TaskHubGrpcWorker(host_address="localhost:4001") as worker:
    worker.add_orchestrator(say_hello)
    worker.add_activity(hello_activity)
    worker.start()
    # worker.stop() is called automatically on exit
```


## Supported patterns

The following orchestration patterns are currently supported.

### Function chaining

An orchestration can chain a sequence of function calls using the following syntax:

```python
# simple activity function that returns a greeting
def hello(ctx: task.ActivityContext, name: str) -> str:
    return f'Hello {name}!'

# orchestrator function that sequences the activity calls
def sequence(ctx: task.OrchestrationContext, _):
    result1 = yield ctx.call_activity(hello, input='Tokyo')
    result2 = yield ctx.call_activity(hello, input='Seattle')
    result3 = yield ctx.call_activity(hello, input='London')

    return [result1, result2, result3]
```

You can find the full sample [here](./examples/activity_sequence.py).

### Fan-out/fan-in

An orchestration can fan-out a dynamic number of function calls in parallel and then fan-in the results using the following syntax:

```python
# activity function for getting the list of work items
def get_work_items(ctx: task.ActivityContext, _) -> List[str]:
    # ...

# activity function for processing a single work item
def process_work_item(ctx: task.ActivityContext, item: str) -> int:
    # ...

# orchestrator function that fans-out the work items and then fans-in the results
def orchestrator(ctx: task.OrchestrationContext, _):
    # the number of work-items is unknown in advance
    work_items = yield ctx.call_activity(get_work_items)

    # fan-out: schedule the work items in parallel and wait for all of them to complete
    tasks = [ctx.call_activity(process_work_item, input=item) for item in work_items]
    results = yield task.when_all(tasks)

    # fan-in: summarize and return the results
    return {'work_items': work_items, 'results': results, 'total': sum(results)}
```

You can find the full sample [here](./examples/fanout_fanin.py).

### Human interaction and durable timers

An orchestration can wait for a user-defined event, such as a human approval event, before proceding to the next step. In addition, the orchestration can create a timer with an arbitrary duration that triggers some alternate action if the external event hasn't been received:

```python
def purchase_order_workflow(ctx: task.OrchestrationContext, order: Order):
    """Orchestrator function that represents a purchase order workflow"""
    # Orders under $1000 are auto-approved
    if order.Cost < 1000:
        return "Auto-approved"

    # Orders of $1000 or more require manager approval
    yield ctx.call_activity(send_approval_request, input=order)

    # Approvals must be received within 24 hours or they will be canceled.
    approval_event = ctx.wait_for_external_event("approval_received")
    timeout_event = ctx.create_timer(timedelta(hours=24))
    winner = yield task.when_any([approval_event, timeout_event])
    if winner == timeout_event:
        return "Canceled"

    # The order was approved
    yield ctx.call_activity(place_order, input=order)
    approval_details = approval_event.get_result()
    return f"Approved by '{approval_details.approver}'"
```

As an aside, you'll also notice that the example orchestration above works with custom business objects. Support for custom business objects includes support for custom classes, custom data classes, and named tuples. Serialization and deserialization of these objects is handled automatically by the SDK.

You can find the full sample [here](./examples/human_interaction.py).

## Feature overview

The following features are currently supported:

### Orchestrations

Orchestrations are implemented using ordinary Python functions that take an `OrchestrationContext` as their first parameter. The `OrchestrationContext` provides APIs for starting child orchestrations, scheduling activities, and waiting for external events, among other things. Orchestrations are fault-tolerant and durable, meaning that they can automatically recover from failures and rebuild their local execution state. Orchestrator functions must be deterministic, meaning that they must always produce the same output given the same input.

### Activities

Activities are implemented using ordinary Python functions that take an `ActivityContext` as their first parameter. Activity functions are scheduled by orchestrations and have at-least-once execution guarantees, meaning that they will be executed at least once but may be executed multiple times in the event of a transient failure. Activity functions are where the real "work" of any orchestration is done.

### Durable timers

Orchestrations can schedule durable timers using the `create_timer` API. These timers are durable, meaning that they will survive orchestrator restarts and will fire even if the orchestrator is not actively in memory. Durable timers can be of any duration, from milliseconds to months.

### Sub-orchestrations

Orchestrations can start child orchestrations using the `call_sub_orchestrator` API. Child orchestrations are useful for encapsulating complex logic and for breaking up large orchestrations into smaller, more manageable pieces.

### External events

Orchestrations can wait for external events using the `wait_for_external_event` API. External events are useful for implementing human interaction patterns, such as waiting for a user to approve an order before continuing.

### Continue-as-new (TODO)

Orchestrations can be continued as new using the `continue_as_new` API. This API allows an orchestration to restart itself from scratch, optionally with a new input.

### Suspend, resume, and terminate

Orchestrations can be suspended using the `suspend_orchestration` client API and will remain suspended until resumed using the `resume_orchestration` client API. A suspended orchestration will stop processing new events, but will continue to buffer any that happen to arrive until resumed, ensuring that no data is lost. An orchestration can also be terminated using the `terminate_orchestration` client API. Terminated orchestrations will stop processing new events and will discard any buffered events.

### Retry policies

Orchestrations can specify retry policies for activities and sub-orchestrations. These policies control how many times and how frequently an activity or sub-orchestration will be retried in the event of a transient error.

#### Creating a retry policy

```python
from datetime import timedelta
from durabletask import task

retry_policy = task.RetryPolicy(
    first_retry_interval=timedelta(seconds=1),     # Initial delay before first retry
    max_number_of_attempts=5,                      # Maximum total attempts (includes first attempt)
    backoff_coefficient=2.0,                       # Exponential backoff multiplier (must be >= 1)
    max_retry_interval=timedelta(seconds=30),      # Cap on retry delay
    retry_timeout=timedelta(minutes=5),            # Total time limit for all retries (optional)
)
```

**Notes:**
- `max_number_of_attempts` **includes the initial attempt**. For example, `max_number_of_attempts=5` means 1 initial attempt + up to 4 retries.
- `retry_timeout` is optional. If omitted or set to `None`, retries continue until `max_number_of_attempts` is reached.
- `backoff_coefficient` controls exponential backoff: delay = `first_retry_interval * (backoff_coefficient ^ retry_number)`, capped by `max_retry_interval`.
- `non_retryable_error_types` (optional) can specify additional exception types to treat as non-retryable (e.g., `[ValueError, TypeError]`). `NonRetryableError` is always non-retryable regardless of this setting.

#### Using retry policies

Apply retry policies to activities or sub-orchestrations:

```python
def my_orchestrator(ctx: task.OrchestrationContext, input):
    # Retry an activity
    result = yield ctx.call_activity(my_activity, input=data, retry_policy=retry_policy)
    
    # Retry a sub-orchestration
    result = yield ctx.call_sub_orchestrator(child_orchestrator, input=data, retry_policy=retry_policy)
```

#### Non-retryable errors

For errors that should not be retried (e.g., validation failures, permanent errors), raise a `NonRetryableError`:

```python
from durabletask.task import NonRetryableError

def my_activity(ctx: task.ActivityContext, input):
    if input is None:
        # This error will bypass retry logic and fail immediately
        raise NonRetryableError("Input cannot be None")
    
    # Transient errors (network, timeouts, etc.) will be retried
    return call_external_service(input)
```

Even with a retry policy configured, `NonRetryableError` will fail immediately without retrying.

#### Error type matching behavior

**Important:** Error type matching uses **exact class name comparison**, not `isinstance()` checks. This is because exception objects are serialized to gRPC protobuf messages, where only the class name (as a string) survives serialization.

**Key implications:**

- **Not inheritance-aware**: If you specify `ValueError` in `non_retryable_error_types`, it will only match exceptions with the exact class name `"ValueError"`. A custom subclass like `CustomValueError(ValueError)` will NOT match.
- **Workaround**: List all exception types explicitly, including subclasses you want to handle.
- **Built-in exception**: `NonRetryableError` is always treated as non-retryable, matched by the name `"NonRetryableError"`.

**Example:**

```python
from datetime import timedelta
from durabletask import task

# Custom exception hierarchy
class ValidationError(ValueError):
    pass

#  This policy ONLY matches exact "ValueError" by name
retry_policy = task.RetryPolicy(
    first_retry_interval=timedelta(seconds=1),
    max_number_of_attempts=3,
    non_retryable_error_types=[ValueError]  # Won't match ValidationError subclass!
)

#  To handle both, list them explicitly:
retry_policy = task.RetryPolicy(
    first_retry_interval=timedelta(seconds=1),
    max_number_of_attempts=3,
    non_retryable_error_types=[ValueError, ValidationError]  # Both converted to name strings
)
```

## Getting Started

### Prerequisites

- Python 3.9
- A Durable Task-compatible sidecar, like [Dapr Workflow](https://docs.dapr.io/developing-applications/building-blocks/workflow/workflow-overview/)

### Installing the Durable Task Python client SDK

Installation is currently only supported from source. Ensure pip, setuptools, and wheel are up-to-date.

```sh
python3 -m pip install --upgrade pip setuptools wheel
```

To install this package from source, clone this repository and run the following command from the project root:

```sh
python3 -m pip install .
```

### Run the samples

See the [examples](./examples) directory for a list of sample orchestrations and instructions on how to run them.

## Development

The following is more information about how to develop this project. Note that development commands require that `make` is installed on your local machine. If you're using Windows, you can install `make` using [Chocolatey](https://chocolatey.org/) or use WSL.

### Generating protobufs

```sh
make gen-proto
```

This will download the `orchestrator_service.proto` from the `microsoft/durabletask-protobuf` repo and compile it using `grpcio-tools`. The version of the source proto file that was downloaded can be found in the file `durabletask/internal/PROTO_SOURCE_COMMIT_HASH`.

### Running unit tests

Unit tests can be run using the following command from the project root.
Unit tests _don't_ require a sidecar process to be running.

To run on a specific python version (eg: 3.11), run the following command from the project root:

```sh
tox -e py311
```

### Running E2E tests

The E2E (end-to-end) tests require a sidecar process to be running.

For non-multi app activities test you can use the Durable Task test sidecar using the following command:

```sh
go install github.com/dapr/durabletask-go@main
durabletask-go --port 4001
```

Certain aspects like multi-app activities require the full dapr runtime to be running.

```shell
dapr init || true

dapr run --app-id test-app --dapr-grpc-port  4001 --resources-path ./examples/components/
```

To run the E2E tests on a specific python version (eg: 3.11), run the following command from the project root:

```sh
tox -e py311 -- e2e
```

## Contributing

This project welcomes contributions and suggestions.  Most contributions require you to agree to a
Contributor License Agreement (CLA) declaring that you have the right to, and actually do, grant us
the rights to use your contribution. For details, visit https://cla.opensource.microsoft.com.

When you submit a pull request, a CLA bot will automatically determine whether you need to provide
a CLA and decorate the PR appropriately (e.g., status check, comment). Simply follow the instructions
provided by the bot. You will only need to do this once across all repos using our CLA.

This project has adopted the [Microsoft Open Source Code of Conduct](https://opensource.microsoft.com/codeofconduct/).
For more information see the [Code of Conduct FAQ](https://opensource.microsoft.com/codeofconduct/faq/) or
contact [opencode@microsoft.com](mailto:opencode@microsoft.com) with any additional questions or comments.

## Trademarks

This project may contain trademarks or logos for projects, products, or services. Authorized use of Microsoft
trademarks or logos is subject to and must follow
[Microsoft's Trademark & Brand Guidelines](https://www.microsoft.com/en-us/legal/intellectualproperty/trademarks/usage/general).
Use of Microsoft trademarks or logos in modified versions of this project must not cause confusion or imply Microsoft sponsorship.
Any use of third-party trademarks or logos are subject to those third-party's policies.
