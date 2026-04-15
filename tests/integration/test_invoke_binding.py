import subprocess
import time
from pathlib import Path

import httpx
import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
BINDING_DIR = REPO_ROOT / 'examples' / 'invoke-binding'

EXPECTED_MESSAGES = [
    '{"id":1,"message":"hello world"}',
    '{"id":2,"message":"hello world"}',
    '{"id":3,"message":"hello world"}',
]


@pytest.fixture()
def kafka():
    subprocess.run(
        'docker compose -f ./docker-compose-single-kafka.yml up -d',
        shell=True,
        cwd=BINDING_DIR,
        check=True,
        capture_output=True,
    )
    time.sleep(30)
    yield
    subprocess.run(
        'docker compose -f ./docker-compose-single-kafka.yml down',
        shell=True,
        cwd=BINDING_DIR,
        check=True,
        capture_output=True,
    )


@pytest.mark.example_dir('invoke-binding')
def test_invoke_binding(dapr, kafka):
    receiver = dapr.start(
        '--app-id receiver --app-protocol grpc --app-port 50051 '
        '--dapr-http-port 3500 --resources-path ./components python3 invoke-input-binding.py',
        wait=5,
    )

    # Publish through the receiver's sidecar (both scripts are infinite,
    # so we reimplement the publisher here with a bounded loop).
    for n in range(1, 4):
        payload = {
            'operation': 'create',
            'data': {'id': n, 'message': 'hello world'},
        }
        response = httpx.post(
            'http://localhost:3500/v1.0/bindings/kafkaBinding', json=payload, timeout=5
        )
        response.raise_for_status()

        time.sleep(1)

    time.sleep(5)
    receiver_output = dapr.stop(receiver)
    for line in EXPECTED_MESSAGES:
        assert line in receiver_output, f'Missing in receiver output: {line}'
