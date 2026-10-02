# Fan-out/Fan-in

## Prerequisites

Follow the [workflow prerequisites](../README.md#prerequisites), then run these commands from the repository root:

```sh
cd examples/workflow/fan-out-fan-in
pip3 install -r ../requirements.txt
```

## Run the example

This example demonstrates how to fan-out a workflow into multiple parallel tasks, and then fan-in the results of those tasks. You can run this sample using the following command:

<!--STEP
name: Run the fan-out/fan-in example
match_order: none
expected_stdout_lines:
  - "Processing work item: 1."
  - "Processing work item: 2."
  - "Processing work item: 3."
  - "Processing work item: 4."
  - "Processing work item: 5."
  - "Processing work item: 6."
  - "Processing work item: 7."
  - "Processing work item: 8."
  - "Processing work item: 9."
  - "Processing work item: 10."
  - "Work item 1 processed. Result: 2."
  - "Work item 2 processed. Result: 4."
  - "Work item 3 processed. Result: 6."
  - "Work item 4 processed. Result: 8."
  - "Work item 5 processed. Result: 10."
  - "Work item 6 processed. Result: 12."
  - "Work item 7 processed. Result: 14."
  - "Work item 8 processed. Result: 16."
  - "Work item 9 processed. Result: 18."
  - "Work item 10 processed. Result: 20."
  - "Final result: 110."
timeout_seconds: 30
-->

```sh
dapr run --app-id wfexample -- python3 fan_out_fan_in.py
```
<!--END_STEP-->

The output of this sample should look like this:

```
Workflow started. Instance ID: 2e656befbb304e758776e30642b75944
Processing work item: 1.
Processing work item: 2.
Processing work item: 3.
Processing work item: 4.
Processing work item: 5.
Processing work item: 6.
Processing work item: 7.
Processing work item: 8.
Processing work item: 9.
Processing work item: 10.
Work item 1 processed. Result: 2.
Work item 2 processed. Result: 4.
Work item 3 processed. Result: 6.
Work item 4 processed. Result: 8.
Work item 5 processed. Result: 10.
Work item 6 processed. Result: 12.
Work item 7 processed. Result: 14.
Work item 8 processed. Result: 16.
Work item 9 processed. Result: 18.
Work item 10 processed. Result: 20.
Final result: 110.
```

Note that the ordering of the work-items is non-deterministic since they are all running in parallel.
