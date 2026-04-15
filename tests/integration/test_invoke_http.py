import pytest

EXPECTED_RECEIVER = [
    'Order received : {"id": 1, "message": "hello world"}',
    'Order error : {"id": 2, "message": "hello world"}',
]

EXPECTED_CALLER = [
    'text/html',
    '{"success": true}',
    '200',
    'error occurred',
    'MY_CODE',
    '503',
]


@pytest.mark.example_dir('invoke-http')
def test_invoke_http(dapr):
    receiver = dapr.start(
        '--app-id invoke-receiver --app-port 8088 --app-protocol http '
        '-- python3 invoke-receiver.py',
        wait=5,
    )
    caller_output = dapr.run(
        '--app-id invoke-caller -- python3 invoke-caller.py',
        timeout=30,
    )
    for line in EXPECTED_CALLER:
        assert line in caller_output, f'Missing in caller output: {line}'

    receiver_output = dapr.stop(receiver)
    for line in EXPECTED_RECEIVER:
        assert line in receiver_output, f'Missing in receiver output: {line}'
