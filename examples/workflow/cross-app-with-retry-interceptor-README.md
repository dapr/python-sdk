# Cross-App Workflow with Default Retry Policy Interceptor

This example demonstrates how to use workflow outbound interceptors to automatically set default retry policies for activities and child workflows.

## Features

- **Default Retry Policies**: Interceptor automatically adds retry policies to activities that don't have one
- **App-Specific Policies**: Different retry policies based on the target `app_id`
- **Policy Preservation**: User-provided retry policies are preserved and not overridden
- **Cross-App Communication**: Demonstrates retry behavior across Dapr app boundaries

## Architecture

- **App1** (`cross-app-with-retry-interceptor-app1.py`):
  - Runs the main workflow
  - Has a custom `DefaultRetryInterceptor` that sets retry policies
  - Calls both local and cross-app activities
  - Demonstrates explicit retry policy specification

- **App2** (`cross-app-with-retry-interceptor-app2.py`):
  - Provides the `remote_activity` for cross-app calls
  - Can simulate failures to test retry behavior

## Interceptor Behavior

The `DefaultRetryInterceptor` in app1:

1. **For cross-app activities** (`app_id='wfexample-retry-app2'`):
   - 3 retry attempts
   - 500ms initial retry interval
   - 5s max retry interval
   - Exponential backoff (coefficient 2.0)

2. **For local activities** (no `app_id` or different app):
   - 2 retry attempts
   - 100ms initial retry interval
   - 2s max retry interval

3. **User-provided policies**: Preserved unchanged

## Setup

### Prerequisites
- Dapr CLI installed
- Python 3.8+
- Dapr Python SDK installed

### Install Dependencies
```bash
pip install dapr-ext-workflow
```

## Running the Example

### Terminal 1: Start App2 (Activity Provider)
```bash
dapr run --app-id wfexample-retry-app2 --dapr-grpc-port 50002 \
  -- python cross-app-with-retry-interceptor-app2.py
```

### Terminal 2: Start App1 (Main Workflow)
```bash
dapr run --app-id wfexample-retry-app1 --dapr-grpc-port 50001 \
  -- python cross-app-with-retry-interceptor-app1.py
```

## Testing Retry Behavior

To see the retry policy in action, you can simulate failures:

### Terminal 1: Start App2 with Failure Simulation
```bash
SIMULATE_FAILURE=true dapr run --app-id wfexample-retry-app2 --dapr-grpc-port 50002 --app-port 5002 \
  -- python cross-app-with-retry-interceptor-app2.py
```

You should see the interceptor's retry policy kick in and retry the failed activity multiple times.

## Expected Output

### App1 Output (Successful Case)
```
app1 - workflow started
[Interceptor] Setting default retry policy for activity local_activity
app1 - calling local_activity
app1 - local_activity called with input: local-call
app1 - local_activity result: local-result-local-call
[Interceptor] Setting cross-app retry policy for activity remote_activity -> wfexample-retry-app2
app1 - calling cross-app activity
app1 - remote_activity result: remote-result-cross-app-call
[Interceptor] Preserving user-provided retry policy for local_activity
app1 - calling activity with explicit retry policy
app1 - explicit retry activity result: local-result-explicit-retry
app1 - workflow completed
```

### App2 Output
```
app2 - starting workflow runtime
app2 - workflow runtime started, waiting...
app2 - remote_activity called with input: cross-app-call
app2 - remote_activity completed successfully
```

## Key Concepts

1. **Interceptor Chain**: Interceptors can inspect and modify requests before they're processed
2. **Retry Policies**: Control how failures are handled with automatic retries
3. **Cross-App Communication**: Activities can be called across different Dapr applications
4. **Graceful Defaults**: Provide sensible defaults while allowing explicit overrides

## Customization

You can customize the retry policies in the `DefaultRetryInterceptor` class:

```python
class DefaultRetryInterceptor(BaseWorkflowOutboundInterceptor):
    def call_activity(self, request: CallActivityRequest, nxt):
        if request.retry_policy is None:
            # Customize your default retry policy here
            retry_policy = wf.RetryPolicy(
                max_number_of_attempts=5,  # More retries
                first_retry_interval=timedelta(seconds=1),
                max_retry_interval=timedelta(seconds=10),
            )
```

## Clean Up

Stop both Dapr applications with Ctrl+C in each terminal.



