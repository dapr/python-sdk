import time
import pytest

EXPECTED_SUBSCRIBER = [
    'Subscriber received: id=1, message="hello world", content_type="application/json"',
    'Subscriber received: id=2, message="hello world", content_type="application/json"',
    'Subscriber received: id=3, message="hello world", content_type="application/json"',
    'Wildcard-Subscriber received: id=4, message="hello world", content_type="application/json"',
    'Wildcard-Subscriber received: id=5, message="hello world", content_type="application/json"',
    'Wildcard-Subscriber received: id=6, message="hello world", content_type="application/json"',
    'Dead-Letter Subscriber received: id=7, message="hello world", content_type="application/json"',
    'Dead-Letter Subscriber. Received via deadletter topic: TOPIC_D_DEAD',
    'Dead-Letter Subscriber. Originally intended topic: TOPIC_D',
    'Subscriber received: TOPIC_CE',
]

EXPECTED_PUBLISHER = [
    "{'id': 1, 'message': 'hello world'}",
    "{'id': 2, 'message': 'hello world'}",
    "{'id': 3, 'message': 'hello world'}",
    'Bulk published 3 events. Failed entries: 0',
]


@pytest.mark.example_dir('pubsub-simple')
def test_pubsub_simple(dapr):
    subscriber = dapr.start(
        '--app-id python-subscriber --app-protocol grpc --app-port 50051 -- python3 subscriber.py',
        wait=5,
    )
    publisher_output = dapr.run(
        '--app-id python-publisher --app-protocol grpc --dapr-grpc-port=3500 '
        '--enable-app-health-check -- python3 publisher.py',
        timeout=30,
    )
    for line in EXPECTED_PUBLISHER:
        assert line in publisher_output, f'Missing in publisher output: {line}'

    time.sleep(5)
    subscriber_output = dapr.stop(subscriber)
    for line in EXPECTED_SUBSCRIBER:
        assert line in subscriber_output, f'Missing in subscriber output: {line}'
