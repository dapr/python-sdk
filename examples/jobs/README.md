# Example - Jobs API

This example demonstrates the [Jobs API](https://docs.dapr.io/developing-applications/building-blocks/jobs/) in Dapr.
It demonstrates the following APIs:
- **schedule_job_alpha1**: Schedule a job to run at specified times
- **get_job_alpha1**: Retrieve details about a scheduled job
- **delete_job_alpha1**: Delete a scheduled job

It includes two examples that showcase different aspects of the Jobs API:

1. **`job_management.py`** - Focuses on job scheduling patterns and management operations
2. **`job_processing.py`** - Shows the complete workflow including job event handling

> **Note:** The Jobs API is currently in Alpha and subject to change. Make sure to use the latest proto bindings.

## Prerequisites

- [Dapr CLI and initialized environment](https://docs.dapr.io/getting-started)
- [Install Python 3.10+](https://www.python.org/downloads/)
- Dapr runtime v1.15+ (Jobs API support)

## Install Dapr python-SDK

<!-- Our CI/CD pipeline automatically installs the correct version, so we can skip this step in the automation -->

```bash
pip3 install dapr dapr-ext-grpc
```

## Run the example

To run this example, the following code can be utilized:

<!-- STEP
name: Run jobs example
expected_stdout_lines:
  - "== APP == 0. Scheduling a simple job without data..."
  - "== APP == ✓ Simple job scheduled successfully"
  - "== APP == 1. Scheduling a recurring job with cron schedule..."
  - "== APP == ✓ Recurring job scheduled successfully"
  - "== APP == 2. Scheduling a one-time job with due_time..."
  - "== APP == ✓ One-time job scheduled successfully"
  - "== APP == 3. Scheduling jobs with failure policies..."
  - "== APP == ✓ Job with drop failure policy scheduled successfully"
  - "== APP == ✓ Job with constant retry policy scheduled successfully"
  - "== APP == 4. Getting job details..."
  - "== APP == ✓ Retrieved job details:"
  - "== APP == 5. Cleaning up - deleting jobs..."
  - "== APP == ✓ Deleted job: simple-job"
  - "== APP == ✓ Deleted job: recurring-hello-job"
  - "== APP == ✓ Deleted job: one-time-hello-job"
  - "== APP == ✓ Deleted job: drop-policy-job"
  - "== APP == ✓ Deleted job: retry-policy-job"
timeout_seconds: 10
-->

```bash
dapr run --app-id jobs-example -- python3 job_management.py
```

<!-- END_STEP -->

## Example 2: Complete Workflow with Job Event Handling

This example (`job_processing.py`) demonstrates the complete Jobs API workflow in a single application that both schedules jobs and handles job events when they trigger. This shows:

- How to register job event handlers using `@app.job_event()` decorators
- How to schedule jobs from the same application that handles them
- How to process job events with structured data
- Complete end-to-end job lifecycle (schedule → trigger → handle)

Run the following command in a terminal/command-prompt:

<!-- STEP
name: Run complete workflow example
expected_stdout_lines:
  - "== APP == Dapr Jobs Example"
  - "== APP == Starting gRPC server on port 50051..."
  - "== APP == Scheduling jobs..."
  - "== APP == ✓ hello-job scheduled"
  - "== APP == ✓ data-job scheduled"
  - "== APP == Jobs scheduled! Waiting for execution..."
  - "== APP == Job event received: hello-job"
  - "== APP == Job data: None"
  - "== APP == Hello job processing completed!"
  - "== APP == Data job event received: data-job"
  - "== APP == Processing data_processing task with priority high"
  - "== APP == Processing 42 items..."
  - "== APP == Data job processing completed!"
background: true
sleep: 15
-->

```bash
# Start the complete workflow example (schedules jobs and handles job events)
dapr run --app-id jobs-workflow --app-protocol grpc --app-port 51054 python3 job_processing.py
```

<!-- END_STEP -->

## Cleanup

<!-- STEP
expected_stdout_lines:
  - '✅  app stopped successfully: jobs-workflow'
name: Shutdown dapr
-->

```bash
dapr stop --app-id jobs-workflow
```

<!-- END_STEP -->

## Example Comparison

| Feature | `job_management.py` | `job_processing.py` |
|---------|---------------------|---------------------|
| **Purpose** | Job scheduling and management | Complete workflow with event handling |
| **Job Scheduling** | ✅ Multiple patterns | ✅ Simple patterns |
| **Job Event Handling** | ❌ No | ✅ Yes |
| **Job Data Processing** | ❌ No | ✅ Yes |
| **Use Case** | Learning job scheduling | Production job processing |
| **Complexity** | Simple | Moderate |

**Use `job_management.py` when:**
- Learning how to schedule different types of jobs
- Testing job scheduling patterns
- Managing jobs without processing them

**Use `job_processing.py` when:**
- Building applications that process job events
- Need complete end-to-end job workflow
- Want to see job event handling in action

The output should be as follows:

```
0. Scheduling a simple job without data...
✓ Simple job scheduled successfully
1. Scheduling a recurring job with cron schedule...
✓ Recurring job scheduled successfully
2. Scheduling a one-time job with due_time...
✓ One-time job scheduled successfully
3. Getting job details...
✓ Retrieved job details:
  - Name: recurring-hello-job
  - Schedule: @every 30s
  - TTL: 5m
  - Data: {'message': 'Hello from recurring job!'}
4. Cleaning up - deleting jobs...
✓ Deleted job: simple-job
✓ Deleted job: recurring-hello-job
✓ Deleted job: one-time-hello-job
```

## Job Scheduling Features

### Schedule Formats

The Jobs API supports multiple schedule formats:

**Cron Expressions (systemd timer style)**
- `"0 30 * * * *"` - Every hour on the half hour
- `"0 15 3 * * *"` - Every day at 03:15

**Human-readable Period Strings**
- `"@every 1h30m"` - Every 1 hour and 30 minutes
- `"@yearly"` or `"@annually"` - Once a year, midnight, Jan. 1st
- `"@monthly"` - Once a month, midnight, first of month
- `"@weekly"` - Once a week, midnight on Sunday
- `"@daily"` or `"@midnight"` - Once a day, midnight
- `"@hourly"` - Once an hour, beginning of hour

### Job Properties

- **name**: Unique identifier for the job
- **schedule**: Cron expression or period string (optional if due_time is provided)
- **due_time**: Specific time for one-shot execution (optional if schedule is provided)
- **repeats**: Number of times to repeat the job (optional)
- **ttl**: Time-to-live for the job (optional)
- **data**: Payload data to send when the job is triggered (optional, empty Any proto used if not provided)
- **failure_policy**: Policy to apply when the job fails to trigger (optional)
- **overwrite**: If true, allows this job to overwrite an existing job with the same name (default: false)

## Job Failure Policies

Jobs can be configured with failure policies that determine what happens when a job fails to trigger:

### DropFailurePolicy

Drops the job when it fails to trigger (no retries):

```python
from dapr.clients import Job, DropFailurePolicy

job = Job(
    name="my-job",
    schedule="@every 30s",
    failure_policy=DropFailurePolicy()
)
```

### ConstantFailurePolicy

Retries the job at constant intervals when it fails to trigger:

```python
from dapr.clients import Job, ConstantFailurePolicy

job = Job(
    name="my-job",
    schedule="@every 30s",
    failure_policy=ConstantFailurePolicy(
        max_retries=3,           # Maximum number of retries (optional)
        interval_seconds=10      # Interval between retries in seconds
    )
)
```

**ConstantFailurePolicy Parameters:**
- **max_retries**: Maximum number of retries. If not specified, retries indefinitely.
- **interval_seconds**: Interval between retries in seconds. Defaults to 30 seconds.

## Handling Job Events

To handle job events when they're triggered, create a callback service using the gRPC extension:

```python
from dapr.ext.grpc import App, JobEvent

app = App()

@app.job_event('my-job')
def handle_my_job(job_event: JobEvent) -> None:
    print(f"Job {job_event.name} triggered!")
    data_str = job_event.get_data_as_string()
    print(f"Job data: {data_str}")
    # Process the job...

app.run(51054)
```

The callback service must:
- Use the `@app.job_event('job-name')` decorator to register handlers
- Accept a `JobEvent` object parameter containing job execution data
- Run on a gRPC port (default 50051) that Dapr can reach

## Additional Information

- The Jobs API is currently in **Alpha** and subject to change
- Jobs are persistent and will survive Dapr sidecar restarts
- Job names must be unique within the Dapr application
- Both `schedule` and `due_time` are optional - if neither is provided, the job will trigger immediately
- Requires Dapr runtime v1.14+ for Jobs API support

For more information about the Jobs API, see:
- [Dapr Jobs Building Block](https://docs.dapr.io/developing-applications/building-blocks/jobs/)
- [Dapr Jobs API Proposal](https://github.com/dapr/proposals/blob/main/0012-BIRS-distributed-scheduler.md)
