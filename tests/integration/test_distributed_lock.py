import pytest

EXPECTED_LINES = [
    'Will try to acquire a lock from lock store named [lockstore]',
    'The lock is for a resource named [example-lock-resource]',
    'The client identifier is [example-client-id]',
    'The lock will expire in 60 seconds.',
    'Lock acquired successfully!!!',
    'We already released the lock so unlocking will not work.',
    'We tried to unlock it anyway and got back [UnlockResponseStatus.lock_does_not_exist]',
]


@pytest.mark.example_dir('distributed_lock')
def test_distributed_lock(dapr):
    output = dapr.run(
        '--app-id=locksapp --app-protocol grpc --resources-path components/ python3 lock.py',
        timeout=10,
    )
    for line in EXPECTED_LINES:
        assert line in output, f'Missing in output: {line}'
