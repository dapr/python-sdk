import json
import threading
import uuid
from concurrent.futures import Future

import pytest

from dapr.clients.grpc._response import TopicEventResponse
from tests.wait_utils import wait_until

STORE = 'statestore'
PUBSUB = 'pubsub'
TOPIC = 'TOPIC_A'
TOPIC_STREAM = 'TOPIC_STREAM'
TOPIC_HANDLER = 'TOPIC_HANDLER'


@pytest.fixture(scope='module')
def client(dapr_env, apps_dir, flush_redis):
    return dapr_env.start_sidecar(
        app_id='test-subscriber',
        grpc_port=50001,
        app_port=50051,
        app_cmd=f'python3 {apps_dir / "pubsub_subscriber.py"}',
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

    for n in range(1, 4):
        key = f'received-{run_id}-{n}'
        data = wait_until(
            lambda k=key: client.get_state(store_name=STORE, key=k).data or None,
            timeout=10,
        )
        msg = json.loads(data)
        assert msg['id'] == n
        assert msg['message'] == 'hello world'


def test_publish_event_succeeds(client):
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


def test_bulk_publish_delivers_all_messages(client):
    run_id = uuid.uuid4().hex
    payloads = [
        json.dumps({'run_id': run_id, 'id': n, 'message': f'bulk-{n}'}) for n in range(1, 4)
    ]

    response = client.publish_events(
        pubsub_name=PUBSUB,
        topic_name=TOPIC,
        data=payloads,
        data_content_type='application/json',
    )
    assert response.failed_entries == []

    for n in range(1, 4):
        key = f'received-{run_id}-{n}'
        data = wait_until(
            lambda k=key: client.get_state(store_name=STORE, key=k).data or None,
            timeout=10,
        )
        msg = json.loads(data)
        assert msg['id'] == n
        assert msg['message'] == f'bulk-{n}'


def test_streaming_subscribe_receives_published_message(client):
    subscription = client.subscribe(pubsub_name=PUBSUB, topic=TOPIC_STREAM)
    try:
        run_id = uuid.uuid4().hex
        client.publish_event(
            pubsub_name=PUBSUB,
            topic_name=TOPIC_STREAM,
            data=json.dumps({'run_id': run_id, 'message': 'streaming hello'}),
            data_content_type='application/json',
        )

        next_message_future: Future = Future()

        def read_next_message() -> None:
            try:
                next_message_future.set_result(subscription.next_message())
            except Exception as exc:
                next_message_future.set_exception(exc)

        threading.Thread(target=read_next_message, daemon=True).start()

        message = next_message_future.result(timeout=10)
        subscription.respond_success(message)

        payload = message.data()
        assert payload['run_id'] == run_id
        assert payload['message'] == 'streaming hello'
    finally:
        subscription.close()


def test_subscribe_with_handler_invokes_callback(client):
    received: list[dict] = []
    handler_done = threading.Event()

    def handler(message) -> TopicEventResponse:
        received.append(message.data())
        if len(received) >= 2:
            handler_done.set()
        return TopicEventResponse('success')

    close_fn = client.subscribe_with_handler(
        pubsub_name=PUBSUB,
        topic=TOPIC_HANDLER,
        handler_fn=handler,
    )
    try:
        run_id = uuid.uuid4().hex
        for n in range(1, 3):
            client.publish_event(
                pubsub_name=PUBSUB,
                topic_name=TOPIC_HANDLER,
                data=json.dumps({'run_id': run_id, 'id': n}),
                data_content_type='application/json',
            )

        assert handler_done.wait(timeout=10), 'handler was not invoked'
        ids = sorted(msg['id'] for msg in received if msg['run_id'] == run_id)
        assert ids == [1, 2]
    finally:
        close_fn()
