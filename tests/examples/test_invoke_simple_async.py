import pytest

EXPECTED_CALLER = [
    'text/plain',
    'INVOKE_RECEIVED',
]

EXPECTED_RECEIVER = [
    '{"id": 1, "message": "hello world"}',
    '{"id": 2, "message": "hello world"}',
    '{"id": 3, "message": "hello world"}',
]


@pytest.mark.example_dir('invoke-simple-async')
def test_invoke_simple_async(dapr):
    dapr.start(
        '--app-id invoke-receiver --app-protocol grpc --app-port 13551 '
        '-- python3 invoke-receiver.py',
    )

    caller_output = dapr.run(
        '--app-id invoke-caller --app-protocol grpc -- python3 invoke-caller.py',
        timeout=30,
    )
    for line in EXPECTED_CALLER:
        assert line in caller_output, f'Missing in caller output: {line}'
    assert caller_output.count('INVOKE_RECEIVED') == 3, 'Expected three concurrent invocations'

    receiver_output = dapr.stop()
    for line in EXPECTED_RECEIVER:
        assert line in receiver_output, f'Missing in receiver output: {line}'
