import httpx
import pytest

EXPECTED_RECEIVER = [
    '{"id":1,"message":"hello world"}',
]


@pytest.mark.example_dir('invoke-simple')
def test_invoke_simple(dapr):
    receiver = dapr.start(
        '--app-id invoke-receiver --app-protocol grpc --app-port 50051 '
        '--dapr-http-port 3500 python3 invoke-receiver.py',
        wait=5,
    )

    # invoke-caller.py runs an infinite loop, so we invoke the method
    # directly through the sidecar HTTP API with a single call.
    resp = httpx.post(
        'http://localhost:3500/v1.0/invoke/invoke-receiver/method/my-method',
        json={'id': 1, 'message': 'hello world'},
        timeout=5,
    )
    resp.raise_for_status()

    assert 'text/plain' in resp.headers.get('content-type', '')
    assert 'INVOKE_RECEIVED' in resp.text

    receiver_output = dapr.stop(receiver)
    for line in EXPECTED_RECEIVER:
        assert line in receiver_output, f'Missing in receiver output: {line}'
