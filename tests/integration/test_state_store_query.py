import subprocess

import pytest

EXPECTED_LINES = [
    '1 {"city": "Seattle", "person": {"id": 1036.0, "org": "Dev Ops"}, "state": "WA"}',
    '4 {"city": "Spokane", "person": {"id": 1042.0, "org": "Dev Ops"}, "state": "WA"}',
    '10 {"city": "New York", "person": {"id": 1054.0, "org": "Dev Ops"}, "state": "NY"}',
    'Token: 3',
    '9 {"city": "San Diego", "person": {"id": 1002.0, "org": "Finance"}, "state": "CA"}',
    '7 {"city": "San Francisco", "person": {"id": 1015.0, "org": "Dev Ops"}, "state": "CA"}',
    '3 {"city": "Sacramento", "person": {"id": 1071.0, "org": "Finance"}, "state": "CA"}',
    'Token: 6',
]


@pytest.fixture()
def mongodb():
    subprocess.run(
        'docker run -d --rm -p 27017:27017 --name mongodb mongo:5',
        shell=True,
        check=True,
        capture_output=True,
    )
    yield
    subprocess.run(
        'docker kill mongodb',
        shell=True,
        capture_output=True,
    )


@pytest.fixture()
def import_data(mongodb, dapr):
    """Import the test dataset into the state store via Dapr."""
    dapr.run(
        '--app-id demo --dapr-http-port 3500 --resources-path components '
        '-- curl -X POST -H "Content-Type: application/json" '
        '-d @dataset.json http://localhost:3500/v1.0/state/statestore',
        timeout=15,
    )


@pytest.mark.example_dir('state_store_query')
def test_state_store_query(dapr, import_data):
    output = dapr.run(
        '--app-id queryexample --resources-path components/ -- python3 state_store_query.py',
        timeout=10,
    )
    for line in EXPECTED_LINES:
        assert line in output, f'Missing in output: {line}'
