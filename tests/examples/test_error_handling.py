import pytest

EXPECTED_LINES = [
    'Status code: StatusCode.INVALID_ARGUMENT',
    "Message: input key/keyPrefix 'key||' can't contain '||'",
    'Error code: DAPR_STATE_ILLEGAL_KEY',
    'Error info(reason): DAPR_STATE_ILLEGAL_KEY',
    'Resource info (resource type): state',
    'Resource info (resource name): statestore',
    'Bad request (field): key||',
    "Bad request (description): input key/keyPrefix 'key||' can't contain '||'",
]


@pytest.mark.example_dir('error_handling')
def test_error_handling(dapr):
    output = dapr.run(
        '--resources-path components -- python3 error_handling.py',
        timeout=10,
    )
    for line in EXPECTED_LINES:
        assert line in output, f'Missing in output: {line}'
