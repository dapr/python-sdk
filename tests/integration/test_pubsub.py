import json
import subprocess
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
    )


def test_published_messages_are_received_by_subscriber(client, wait_until):
    run_id = uuid.uuid4().hex
    for n in range(1, 4):
        client.publish_event(
            pubsub_name=PUBSUB,
            topic_name=TOPIC,
            data=json.dumps({'run_id': run_id, 'id': n, 'message': 'hello world'}),
            data_content_type='application/json',
        )

    for n in range(1, 4):
        key = f'received-{run_id}-{n}'
        data = wait_until(
            lambda k=key: client.get_state(store_name=STORE, key=k).data or None,
            timeout=10,
        )
        msg = json.loads(data)
        assert msg['id'] == n
        assert msg['message'] == 'hello world'


def test_publish_event_succeeds(client, wait_until):
    run_id = uuid.uuid4().hex
    client.publish_event(
        pubsub_name=PUBSUB,
        topic_name=TOPIC,
        data=json.dumps({'run_id': run_id, 'id': 99, 'message': 'smoke test'}),
        data_content_type='application/json',
    )

    key = f'received-{run_id}-99'
    data = wait_until(
        lambda: client.get_state(store_name=STORE, key=key).data or None,
        timeout=10,
    )
    msg = json.loads(data)
    assert msg['id'] == 99
    assert msg['message'] == 'smoke test'
