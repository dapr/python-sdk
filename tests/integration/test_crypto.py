from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
CRYPTO_DIR = REPO_ROOT / 'examples' / 'crypto'

EXPECTED_COMMON = [
    'Running encrypt/decrypt operation on string',
    'Decrypted the message, got 24 bytes',
    'The secret is "passw0rd"',
    'Running encrypt/decrypt operation on file',
    'Wrote encrypted data to encrypted.out',
    'Wrote decrypted data to decrypted.out.jpg',
]


@pytest.fixture()
def crypto_artifacts():
    """Clean up output files written by the crypto example on teardown.

    Example RSA and AES keys are in ``examples/crypto/keys/``.
    """
    yield
    (CRYPTO_DIR / 'encrypted.out').unlink(missing_ok=True)
    (CRYPTO_DIR / 'decrypted.out.jpg').unlink(missing_ok=True)


@pytest.mark.example_dir('crypto')
def test_crypto(dapr, crypto_artifacts):
    output = dapr.run(
        '--app-id crypto --resources-path ./components/ -- python3 crypto.py',
        timeout=30,
    )
    assert 'Running gRPC client synchronous API' in output
    for line in EXPECTED_COMMON:
        assert line in output, f'Missing in output: {line}'


@pytest.mark.example_dir('crypto')
def test_crypto_async(dapr, crypto_artifacts):
    output = dapr.run(
        '--app-id crypto-async --resources-path ./components/ -- python3 crypto-async.py',
        timeout=30,
    )
    assert 'Running gRPC client asynchronous API' in output
    for line in EXPECTED_COMMON:
        assert line in output, f'Missing in output: {line}'
