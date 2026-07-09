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

KAFKA_TOPIC = 'sample'


def _wait_for_kafka_topic(topic: str, timeout: float = 120) -> None:
    """Polls the broker until the auto-created topic is listable.

    ``docker compose up -d`` returns once containers are created, but the
    wurstmeister Kafka image takes several seconds of broker registration
    before it can serve metadata. Without this wait, daprd races the broker
    and fails component init with "client has run out of available brokers".
    """
    list_topics_command = (
        'docker',
        'compose',
        '-f',
        './docker-compose-single-kafka.yml',
        'exec',
        '-T',
        'kafka',
        'kafka-topics.sh',
        '--bootstrap-server',
        'localhost:9092',
        '--list',
    )
    deadline = time.monotonic() + timeout
    last_output = ''
    while time.monotonic() < deadline:
        result = subprocess.run(
            list_topics_command,
            cwd=BINDING_DIR,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            timeout=30,
        )
        last_output = result.stdout
        if result.returncode == 0 and topic in result.stdout.split():
            return
        time.sleep(1)
    pytest.fail(f'Kafka topic {topic!r} not available after {timeout}s:\n{last_output}')


@pytest.fixture()
def kafka():
    try:
        subprocess.run(
            ('docker', 'compose', '-f', './docker-compose-single-kafka.yml', 'up', '-d'),
            cwd=BINDING_DIR,
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            timeout=120,
        )
    except subprocess.TimeoutExpired as e:
        output = (e.stdout or b'').decode(errors='replace')
        pytest.fail(f'Timed out starting Kafka:\n{output}')

    _wait_for_kafka_topic(KAFKA_TOPIC)

    yield

    try:
        subprocess.run(
            ('docker', 'compose', '-f', './docker-compose-single-kafka.yml', 'down'),
            cwd=BINDING_DIR,
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            timeout=120,
        )
    except subprocess.TimeoutExpired as e:
        output = (e.stdout or b'').decode(errors='replace')
        pytest.fail(f'Timed out stopping Kafka:\n{output}')


@pytest.mark.example_dir('invoke-binding')
def test_invoke_binding(dapr, kafka):
    dapr.start(
        '--app-id receiver --app-protocol grpc --app-port 50051 '
        '--dapr-http-port 3500 --resources-path ./components -- python3 invoke-input-binding.py',
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

    receiver_output = dapr.stop()
    for line in EXPECTED_MESSAGES:
        assert line in receiver_output, f'Missing in receiver output: {line}'
