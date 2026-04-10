import subprocess
import time

import pytest


EXPECTED_LINES = [
    'Got key=orderId1 value=100 version=1 metadata={}',
    'Got key=orderId2 value=200 version=1 metadata={}',
    'Subscribe key=orderId2 value=210 version=2 metadata={}',
    'Unsubscribed successfully? True',
]


@pytest.fixture()
def redis_config():
    """Seed configuration values in Redis before the test."""
    subprocess.run(
        'docker exec dapr_redis redis-cli SET orderId1 "100||1"',
        shell=True,
        check=True,
        capture_output=True,
    )
    subprocess.run(
        'docker exec dapr_redis redis-cli SET orderId2 "200||1"',
        shell=True,
        check=True,
        capture_output=True,
    )


@pytest.mark.example_dir('configuration')
def test_configuration(dapr, redis_config):
    proc = dapr.start(
        '--app-id configexample --resources-path components/ -- python3 configuration.py',
        wait=5,
    )
    # Update Redis to trigger the subscription notification
    subprocess.run(
        'docker exec dapr_redis redis-cli SET orderId2 "210||2"',
        shell=True,
        check=True,
        capture_output=True,
    )
    # configuration.py sleeps 10s after subscribing before it unsubscribes.
    # Wait long enough for the full script to finish.
    time.sleep(10)

    output = dapr.stop(proc)
    for line in EXPECTED_LINES:
        assert line in output, f'Missing in output: {line}'
