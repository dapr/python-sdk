import pytest

EXPECTED_RECEIVER = [
    'SOME_DATA',
]

EXPECTED_CALLER = [
    'isSuccess: true',
    'code: 200',
    'message: "Hello World - Success!"',
]


@pytest.mark.example_dir('invoke-custom-data')
def test_invoke_custom_data(dapr):
    receiver = dapr.start(
        '--app-id invoke-receiver --app-protocol grpc --app-port 50051 python3 invoke-receiver.py',
        wait=5,
    )
    caller_output = dapr.run(
        '--app-id invoke-caller --app-protocol grpc python3 invoke-caller.py',
        timeout=30,
    )
    for line in EXPECTED_CALLER:
        assert line in caller_output, f'Missing in caller output: {line}'

    receiver_output = dapr.stop(receiver)
    for line in EXPECTED_RECEIVER:
        assert line in receiver_output, f'Missing in receiver output: {line}'
