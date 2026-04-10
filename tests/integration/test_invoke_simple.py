import json
import urllib.request

import pytest

EXPECTED_RECEIVER = [
    '{"id": 1, "message": "hello world"}',
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
    req_data = json.dumps({'id': 1, 'message': 'hello world'}).encode()
    req = urllib.request.Request(
        'http://localhost:3500/v1.0/invoke/invoke-receiver/method/my-method',
        data=req_data,
        headers={'Content-Type': 'application/json'},
    )
    with urllib.request.urlopen(req) as resp:
        content_type = resp.headers.get('Content-Type', '')
        body = resp.read().decode()

    assert 'text/plain' in content_type
    assert 'INVOKE_RECEIVED' in body

    receiver_output = dapr.stop(receiver)
    for line in EXPECTED_RECEIVER:
        assert line in receiver_output, f'Missing in receiver output: {line}'
