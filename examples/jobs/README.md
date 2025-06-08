# Example - Jobs API

This example demonstrates the [Jobs API](https://docs.dapr.io/developing-applications/building-blocks/scheduler/) in Dapr.
It demonstrates the following APIs:
- **schedule_job_alpha1**: Schedule a job to run at specified times
- **get_job_alpha1**: Retrieve details about a scheduled job
- **delete_job_alpha1**: Delete a scheduled job

It creates a client using `DaprClient` and calls all the Jobs API methods available as example.

> **Note:** The Jobs API is currently in Alpha and subject to change. Make sure to use the latest proto bindings.

## Prerequisites

- [Dapr CLI and initialized environment](https://docs.dapr.io/getting-started)
- [Install Python 3.9+](https://www.python.org/downloads/)
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
  - "== APP == 3. Getting job details..."
  - "== APP == ✓ Retrieved job details:"
  - "== APP == 4. Cleaning up - deleting jobs..."
  - "== APP == ✓ Deleted job: simple-job"
  - "== APP == ✓ Deleted job: recurring-hello-job"
  - "== APP == ✓ Deleted job: one-time-hello-job"
timeout_seconds: 10
-->

```bash
dapr run --app-id jobs-example -- python3 simple_job.py
```

<!-- END_STEP -->

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
- **overwrite**: If true, allows this job to overwrite an existing job with the same name (default: false)


## Additional Information

- The Jobs API is currently in **Alpha** and subject to change
- Jobs are persistent and will survive Dapr sidecar restarts
- Job names must be unique within the Dapr application
- Both `schedule` and `due_time` are optional - if neither is provided, the job will trigger immediately
- Requires Dapr runtime v1.14+ for Jobs API support

For more information about the Jobs API, see:
- [Dapr Scheduler Building Block](https://docs.dapr.io/developing-applications/building-blocks/scheduler/)
- [Dapr Jobs API Proposal](https://github.com/dapr/proposals/blob/main/0012-BIRS-distributed-scheduler.md)
