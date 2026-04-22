import pytest

EXPECTED_MANAGEMENT = [
    '0. Scheduling a simple job without data...',
    'Simple job scheduled successfully',
    '1. Scheduling a recurring job with cron schedule...',
    'Recurring job scheduled successfully',
    '2. Scheduling a one-time job with due_time...',
    'One-time job scheduled successfully',
    '3. Scheduling jobs with failure policies...',
    'Job with drop failure policy scheduled successfully',
    'Job with constant retry policy scheduled successfully',
    '4. Getting job details...',
    'Retrieved job details:',
    '5. Cleaning up - deleting jobs...',
    'Deleted job: simple-job',
    'Deleted job: recurring-hello-job',
    'Deleted job: one-time-hello-job',
    'Deleted job: drop-policy-job',
    'Deleted job: retry-policy-job',
]

EXPECTED_PROCESSING = [
    'Dapr Jobs Example',
    'Starting gRPC server on port 50051...',
    'Scheduling jobs...',
    'hello-job scheduled',
    'data-job scheduled',
    'Jobs scheduled! Waiting for execution...',
    'Job event received: hello-job',
    'Data job event received: data-job',
]


@pytest.mark.example_dir('jobs')
def test_job_management(dapr):
    output = dapr.run('--app-id jobs-example -- python3 job_management.py', timeout=30)
    for line in EXPECTED_MANAGEMENT:
        assert line in output, f'Missing in output: {line}'


@pytest.mark.example_dir('jobs')
def test_job_processing(dapr):
    dapr.start(
        '--app-id jobs-workflow --app-protocol grpc --app-port 50051 -- python3 job_processing.py',
        wait=15,
    )
    output = dapr.stop()
    for line in EXPECTED_PROCESSING:
        assert line in output, f'Missing in output: {line}'
