import pytest

EXPECTED_CALLER = [
    'Greeter client received: Hello, you!',
]


@pytest.mark.example_dir('grpc_proxying')
def test_grpc_proxying(dapr):
    dapr.start(
        '--app-id invoke-receiver --app-protocol grpc --app-port 50051 '
        '--config config.yaml -- python invoke-receiver.py',
        wait=5,
    )
    caller_output = dapr.run(
        '--app-id invoke-caller --dapr-grpc-port 50007 --config config.yaml -- python invoke-caller.py',
        timeout=30,
    )
    for line in EXPECTED_CALLER:
        assert line in caller_output, f'Missing in caller output: {line}'

    dapr.stop()
