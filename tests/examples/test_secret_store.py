import pytest

EXPECTED_LINES = [
    "{'secretKey': 'secretValue'}",
    "[('random', {'random': 'randomValue'}), ('secretKey', {'secretKey': 'secretValue'})]",
    "{'random': 'randomValue'}",
]

EXPECTED_LINES_WITH_ACL = [
    "{'secretKey': 'secretValue'}",
    "[('secretKey', {'secretKey': 'secretValue'})]",
    'Got expected error for accessing random key',
]


@pytest.mark.example_dir('secret_store')
def test_secret_store(dapr):
    output = dapr.run(
        '--app-id=secretsapp --app-protocol grpc --resources-path components/ -- python3 example.py',
        timeout=30,
    )
    for line in EXPECTED_LINES:
        assert line in output, f'Missing in output: {line}'


@pytest.mark.example_dir('secret_store')
def test_secret_store_with_access_control(dapr):
    output = dapr.run(
        '--app-id=secretsapp --app-protocol grpc --config config.yaml --resources-path components/ -- python3 example.py',
        timeout=30,
    )
    for line in EXPECTED_LINES_WITH_ACL:
        assert line in output, f'Missing in output: {line}'
