# Examples

This directory contains examples of how to author durable orchestrations using the Durable Task Python SDK.

## Prerequisites

All the examples assume that you have a Durable Task-compatible sidecar running locally. There are two options for this:

1. Install the latest version of the [Dapr CLI](https://docs.dapr.io/getting-started/install-dapr-cli/), which contains and exposes an embedded version of the Durable Task engine. The setup process (which requires Docker) will configure the workflow engine to store state in a local Redis container.

2. Run the [Durable Task Sidecar](https://github.com/dapr/durabletask-go) project locally (requires Go 1.18 or higher). Orchestration state will be stored in a local sqlite database.
    ```sh
    go install github.com/dapr/durabletask-go@main
    durabletask-go --port 4001
    ```

## Automated Testing

These examples can be tested automatically using [mechanical-markdown](https://github.com/dapr/mechanical-markdown), which validates that the examples run correctly and produce expected output.

To install mechanical-markdown:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ../.
pip install mechanical-markdown
```

To see what commands would be run without executing them:

```bash
mm.py -d README.md
```

To run all examples and validate their output:

```bash
mm.py README.md
```

## Running the Examples

With one of the sidecars running, you can execute any of the examples in this directory using `python3`:

```sh
python3 ./activity_sequence.py
```

In some cases, the sample may require command-line parameters or user inputs. In these cases, the sample will print out instructions on how to proceed.

### Activity Sequence Example

This example demonstrates the function chaining pattern, where an orchestrator schedules three activity calls in a sequence.

<!-- STEP
name: Run activity sequence example
output_match_mode: substring
expected_stdout_lines:
  - '"Hello Tokyo!", "Hello Seattle!", "Hello London!"'
-->

```bash
python activity_sequence.py
```

<!-- END_STEP -->

### Fan-out/Fan-in Example

This example demonstrates parallel execution, where an orchestrator schedules a dynamic number of activity calls in parallel, waits for all of them to complete, and then performs an aggregation on the results.

<!-- STEP
name: Run fan-out/fan-in example
output_match_mode: substring
expected_stdout_lines:
  - "Orchestration completed! Result"
-->

```bash
python fanout_fanin.py
```

<!-- END_STEP -->

### Human Interaction Example

This example demonstrates how an orchestrator can wait for external events (like human approval) with a timeout. If the approval isn't received within the specified timeout, the order is automatically cancelled.

<!-- STEP
name: Run human interaction example with auto-approval
output_match_mode: substring
expected_stdout_lines:
  - "Approved by 'PYTHON-CI'"
-->

```bash
{ sleep 2; printf '\n'; } | python human_interaction.py --timeout 20 --approver PYTHON-CI
```

<!-- END_STEP -->

## List of examples

- [Activity sequence](./activity_sequence.py): Orchestration that schedules three activity calls in a sequence.
- [Fan-out/fan-in](./fanout_fanin.py): Orchestration that schedules a dynamic number of activity calls in parallel, waits for all of them to complete, and then performs an aggregation on the results.
- [Human interaction](./human_interaction.py): Orchestration that waits for a human to approve an order before continuing.
