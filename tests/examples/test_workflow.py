import pytest

EXPECTED_TASK_CHAINING = [
    'Step 1: Received input: 42.',
    'Step 2: Received input: 43.',
    'Step 3: Received input: 86.',
    'Workflow completed! Status: WorkflowStatus.COMPLETED',
]

EXPECTED_FAN_OUT_FAN_IN = [
    'Final result: 110.',
]

EXPECTED_SIMPLE = [
    'Hi Counter!',
    'New counter value is: 1!',
    'New counter value is: 11!',
    'Retry count value is: 0!',
    'Retry count value is: 1! This print statement verifies retry',
    'Get response from hello_world_wf after pause call: SUSPENDED',
    'Get response from hello_world_wf after resume call: RUNNING',
    'New counter value is: 111!',
    'New counter value is: 1111!',
    'Workflow completed! Result: Completed',
]


@pytest.mark.example_dir('workflow')
def test_task_chaining(dapr):
    output = dapr.run('--app-id workflow-task-chaining -- python3 task_chaining.py', timeout=30)
    for line in EXPECTED_TASK_CHAINING:
        assert line in output, f'Missing in output: {line}'


@pytest.mark.example_dir('workflow')
def test_fan_out_fan_in(dapr):
    output = dapr.run('--app-id workflow-fan-out-fan-in -- python3 fan_out_fan_in.py', timeout=60)
    for line in EXPECTED_FAN_OUT_FAN_IN:
        assert line in output, f'Missing in output: {line}'


@pytest.mark.example_dir('workflow')
def test_simple_workflow(dapr):
    output = dapr.run('--app-id workflow-simple -- python3 simple.py', timeout=60)
    for line in EXPECTED_SIMPLE:
        assert line in output, f'Missing in output: {line}'


EXPECTED_HISTORY_PROPAGATION = [
    '*** validating merchant merchant-42',
    "*** process_payment received parent context for merchant 'merchant-42'",
    '*** log_summary saw parent on app',
    'validate_merchant -> completed=True output={"merchant_id": "merchant-42", "valid": true}',
    '*** workflow completed: status=COMPLETED',
]


@pytest.mark.example_dir('workflow')
def test_history_propagation(dapr):
    output = dapr.run(
        '--app-id workflow-history-propagation -- python3 history_propagation.py',
        timeout=60,
    )
    for line in EXPECTED_HISTORY_PROPAGATION:
        assert line in output, f'Missing in output: {line}'


# Defaults: 5 async activities, 2048B in / 1024B out each, so 5 * 1024 = 5120 bytes aggregated.
EXPECTED_ASYNC_ACTIVITIES = [
    '[async] payload 0: 2048B in -> 1024B out',
    '[sync] 5 results, 5120 bytes',
    'Workflow completed! Status: COMPLETED',
    'Workflow result: 5 results, 5120 bytes',
]


@pytest.mark.example_dir('workflow')
def test_async_activities(dapr):
    output = dapr.run(
        '--app-id workflow-async-activities -- python3 async_activities.py',
        timeout=60,
    )
    for line in EXPECTED_ASYNC_ACTIVITIES:
        assert line in output, f'Missing in output: {line}'
