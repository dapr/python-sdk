import pytest

EXPECTED_LINES = [
    'State store has successfully saved value_1 with key_1 as key',
    'Cannot save due to bad etag. ErrorCode=StatusCode.ABORTED',
    'State store has successfully saved value_2 with key_2 as key',
    'State store has successfully saved value_3 with key_3 as key',
    'Cannot save bulk due to bad etags. ErrorCode=StatusCode.ABORTED',
    "Got value=b'value_1' eTag=1",
    "Got items with etags: [(b'value_1_updated', '2'), (b'value_2', '2')]",
    'Transaction with outbox pattern executed successfully!',
    "Got value after outbox pattern: b'val1'",
    "Got values after transaction delete: [b'', b'']",
    "Got value after delete: b''",
]


@pytest.mark.example_dir('state_store')
def test_state_store(dapr):
    output = dapr.run(
        '--resources-path components/ -- python3 state_store.py',
        timeout=30,
    )
    for line in EXPECTED_LINES:
        assert line in output, f'Missing in output: {line}'
