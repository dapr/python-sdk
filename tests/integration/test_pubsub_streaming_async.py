import pytest

EXPECTED_SUBSCRIBER = [
    "Processing message: {'id': 1, 'message': 'hello world'} from TOPIC_B1...",
    "Processing message: {'id': 2, 'message': 'hello world'} from TOPIC_B1...",
    "Processing message: {'id': 3, 'message': 'hello world'} from TOPIC_B1...",
    "Processing message: {'id': 4, 'message': 'hello world'} from TOPIC_B1...",
    "Processing message: {'id': 5, 'message': 'hello world'} from TOPIC_B1...",
    'Closing subscription...',
]

EXPECTED_HANDLER_SUBSCRIBER = [
    "Processing message: {'id': 1, 'message': 'hello world'} from TOPIC_B2...",
    "Processing message: {'id': 2, 'message': 'hello world'} from TOPIC_B2...",
    "Processing message: {'id': 3, 'message': 'hello world'} from TOPIC_B2...",
    "Processing message: {'id': 4, 'message': 'hello world'} from TOPIC_B2...",
    "Processing message: {'id': 5, 'message': 'hello world'} from TOPIC_B2...",
    'Closing subscription...',
]

EXPECTED_PUBLISHER = [
    "{'id': 1, 'message': 'hello world'}",
    "{'id': 2, 'message': 'hello world'}",
    "{'id': 3, 'message': 'hello world'}",
    "{'id': 4, 'message': 'hello world'}",
    "{'id': 5, 'message': 'hello world'}",
]


@pytest.mark.example_dir('pubsub-streaming-async')
def test_pubsub_streaming_async(dapr):
    dapr.start(
        '--app-id python-subscriber --app-protocol grpc -- python3 subscriber.py --topic=TOPIC_B1',
        wait=5,
    )
    publisher_output = dapr.run(
        '--app-id python-publisher --app-protocol grpc --dapr-grpc-port=3500 '
        '--enable-app-health-check -- python3 publisher.py --topic=TOPIC_B1',
        timeout=30,
    )
    for line in EXPECTED_PUBLISHER:
        assert line in publisher_output, f'Missing in publisher output: {line}'

    subscriber_output = dapr.stop()
    for line in EXPECTED_SUBSCRIBER:
        assert line in subscriber_output, f'Missing in subscriber output: {line}'


@pytest.mark.example_dir('pubsub-streaming-async')
def test_pubsub_streaming_async_handler(dapr):
    dapr.start(
        '--app-id python-subscriber --app-protocol grpc -- python3 subscriber-handler.py --topic=TOPIC_B2',
        wait=5,
    )
    publisher_output = dapr.run(
        '--app-id python-publisher --app-protocol grpc --dapr-grpc-port=3500 '
        '--enable-app-health-check -- python3 publisher.py --topic=TOPIC_B2',
        timeout=30,
    )
    for line in EXPECTED_PUBLISHER:
        assert line in publisher_output, f'Missing in publisher output: {line}'

    subscriber_output = dapr.stop()
    for line in EXPECTED_HANDLER_SUBSCRIBER:
        assert line in subscriber_output, f'Missing in subscriber output: {line}'
