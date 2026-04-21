import pytest

EXPECTED_CALLER = [
    'application/json',
    'SAY',
    'text/plain',
    'SLEEP',
    'Trace ID matches after forwarding',
]


@pytest.mark.example_dir('w3c-tracing')
def test_w3c_tracing(dapr):
    dapr.start(
        '--app-id invoke-receiver --app-protocol grpc --app-port 3001 -- python3 invoke-receiver.py',
        wait=5,
    )
    caller_output = dapr.run(
        '--app-id invoke-caller --app-protocol grpc -- python3 invoke-caller.py',
        timeout=30,
    )
    for line in EXPECTED_CALLER:
        assert line in caller_output, f'Missing in caller output: {line}'

    dapr.stop()
