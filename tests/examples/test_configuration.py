import time

import pytest

EXPECTED_LINES = [
    'Got key=orderId1 value=100 version=1 metadata={}',
    'Got key=orderId2 value=200 version=1 metadata={}',
    'Subscribe key=orderId2 value=210 version=2 metadata={}',
    'Unsubscribed successfully? True',
]


@pytest.mark.example_dir('configuration')
def test_configuration(dapr, redis_set_config):
    redis_set_config('orderId1', '100')
    redis_set_config('orderId2', '200')

    dapr.start(
        '--app-id configexample --resources-path components/ -- python3 configuration.py',
    )
    # Update Redis to trigger the subscription notification
    redis_set_config('orderId2', '210', version=2)
    # configuration.py sleeps 10s after subscribing before it unsubscribes.
    # Wait long enough for the full script to finish.
    time.sleep(10)

    output = dapr.stop()
    for line in EXPECTED_LINES:
        assert line in output, f'Missing in output: {line}'
