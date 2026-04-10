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
    output = dapr.run('-- python3 task_chaining.py', timeout=30)
    for line in EXPECTED_TASK_CHAINING:
        assert line in output, f'Missing in output: {line}'


@pytest.mark.example_dir('workflow')
def test_fan_out_fan_in(dapr):
    output = dapr.run('-- python3 fan_out_fan_in.py', timeout=60)
    for line in EXPECTED_FAN_OUT_FAN_IN:
        assert line in output, f'Missing in output: {line}'


@pytest.mark.example_dir('workflow')
def test_simple_workflow(dapr):
    output = dapr.run('-- python3 simple.py', timeout=60)
    for line in EXPECTED_SIMPLE:
        assert line in output, f'Missing in output: {line}'
