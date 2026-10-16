import pytest

EXPECTED_SUBSCRIBER = [
    'Subscriber received: id=1, message="hello world", content_type="application/json"',
    'Subscriber received: id=2, message="hello world", content_type="application/json"',
    'Subscriber received: id=3, message="hello world", content_type="application/json"',
    'Other-Subscriber received: id=4, message="hello world", content_type="application/json"',
    'Subscriber received: id=20, message="bulk event 1", content_type="application/json"',
    'Subscriber received: id=21, message="bulk event 2", content_type="application/json"',
    'Subscriber received: id=22, message="bulk event 3", content_type="application/json"',
]

EXPECTED_PUBLISHER = [
    "{'id': 1, 'message': 'hello world'}",
    "{'id': 2, 'message': 'hello world'}",
    "{'id': 3, 'message': 'hello world'}",
    "{'id': 4, 'message': 'hello world'}",
    'Bulk published 3 events. Failed entries: 0',
]


@pytest.mark.example_dir('pubsub-simple-async')
def test_pubsub_simple_async(dapr):
    dapr.start(
        '--app-id python-subscriber --app-protocol grpc --app-port 13551 '
        '--enable-app-health-check --app-health-probe-interval 1 -- python3 subscriber.py',
    )
    publisher_output = dapr.run(
        '--app-id python-publisher --app-protocol grpc -- python3 publisher.py',
        timeout=30,
    )
    for line in EXPECTED_PUBLISHER:
        assert line in publisher_output, f'Missing in publisher output: {line}'

    subscriber_output = dapr.stop()
    for line in EXPECTED_SUBSCRIBER:
        assert line in subscriber_output, f'Missing in subscriber output: {line}'
