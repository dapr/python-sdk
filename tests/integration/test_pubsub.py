import json
import subprocess
import time
import uuid

import pytest

STORE = 'statestore'
PUBSUB = 'pubsub'
TOPIC = 'TOPIC_A'
REDIS_CONTAINER = 'dapr_redis'


def _flush_redis() -> None:
    """Flush the Dapr Redis instance to prevent state leaking between runs.

    Both the state store and the pubsub component point at the same
    ``dapr_redis`` container (see ``tests/integration/components/``), so a
    previous run's ``received-*`` keys could otherwise satisfy this test's
    assertions even if no new message was delivered.
    """
    subprocess.run(
        args=('docker', 'exec', REDIS_CONTAINER, 'redis-cli', 'FLUSHDB'),
        check=True,
        capture_output=True,
        timeout=10,
    )


@pytest.fixture(scope='module')
def client(dapr_env, apps_dir):
    _flush_redis()
    return dapr_env.start_sidecar(
        app_id='test-subscriber',
        grpc_port=50001,
        app_port=50051,
        app_cmd=f'python3 {apps_dir / "pubsub_subscriber.py"}',
        wait=10,
    )


def test_published_messages_are_received_by_subscriber(client):
    run_id = uuid.uuid4().hex
    for n in range(1, 4):
        client.publish_event(
            pubsub_name=PUBSUB,
            topic_name=TOPIC,
            data=json.dumps({'run_id': run_id, 'id': n, 'message': 'hello world'}),
            data_content_type='application/json',
        )
        time.sleep(1)

    time.sleep(3)

    for n in range(1, 4):
        state = client.get_state(store_name=STORE, key=f'received-{run_id}-{n}')
        assert state.data != b'', f'Subscriber did not receive message {n}'
        msg = json.loads(state.data)
        assert msg['id'] == n
        assert msg['message'] == 'hello world'


def test_publish_event_succeeds(client):
    """Verify publish_event does not raise on a valid topic."""
    client.publish_event(
        pubsub_name=PUBSUB,
        topic_name=TOPIC,
        data=json.dumps({'run_id': uuid.uuid4().hex, 'id': 99, 'message': 'smoke test'}),
        data_content_type='application/json',
    )
