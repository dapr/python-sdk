import subprocess
from pathlib import Path

import httpx
import pytest

EXAMPLES_DIR = Path(__file__).resolve().parent.parent.parent / 'examples'

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
    # Remove leftover container from a previous crashed run
    subprocess.run(('docker', 'rm', '-f', 'pytest-mongodb'), capture_output=True)
    subprocess.run(
        ('docker', 'run', '-d', '--rm', '-p', '27017:27017', '--name', 'pytest-mongodb', 'mongo:5'),
        check=True,
        capture_output=True,
    )
    yield
    subprocess.run(('docker', 'rm', '-f', 'pytest-mongodb'), capture_output=True)


@pytest.fixture()
def import_data(mongodb, dapr):
    """Seed the test dataset via Dapr's state API.

    The seeding has to go through a Dapr sidecar, not directly to MongoDB:
    ``state.mongodb`` wraps every value as ``{_id, value, etag, _ttl}`` (see
    ``components-contrib/state/mongodb/mongodb.go``), and the query example
    reads these back through the same component. Writing raw documents with
    pymongo would skip that encoding and the query would return nothing.
    """
    dapr.start('--app-id demo --dapr-http-port 3500 --resources-path components', wait=5)
    dataset = (EXAMPLES_DIR / 'state_store_query' / 'dataset.json').read_text()
    httpx.post(
        'http://localhost:3500/v1.0/state/statestore',
        content=dataset,
        headers={'Content-Type': 'application/json'},
        timeout=10,
    ).raise_for_status()
    dapr.stop()


@pytest.mark.example_dir('state_store_query')
def test_state_store_query(dapr, import_data):
    output = dapr.run(
        '--app-id queryexample --resources-path components/ -- python3 state_store_query.py',
        timeout=10,
    )
    for line in EXPECTED_LINES:
        assert line in output, f'Missing in output: {line}'
