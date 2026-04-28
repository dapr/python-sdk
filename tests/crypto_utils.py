from __future__ import annotations

import secrets
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

RSA_KEY_FILENAME = 'rsa-private-key.pem'
SYMMETRIC_KEY_FILENAME = 'symmetric-key-256'

_RSA_KEY_SIZE = 4096
_SYMMETRIC_KEY_BYTES = 32


def write_test_keys(target_dir: Path) -> None:
    """Write a fresh 4096-bit RSA private key (PKCS8 PEM) and a 256-bit AES key.

    File names match those expected by ``examples/crypto/crypto.py`` and the
    ``cryptostore.yaml`` component used by the integration tests.
    """
    target_dir.mkdir(parents=True, exist_ok=True)

    rsa_key = rsa.generate_private_key(public_exponent=65537, key_size=_RSA_KEY_SIZE)
    rsa_pem = rsa_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )
    (target_dir / RSA_KEY_FILENAME).write_bytes(rsa_pem)
    (target_dir / SYMMETRIC_KEY_FILENAME).write_bytes(secrets.token_bytes(_SYMMETRIC_KEY_BYTES))


def remove_test_keys(target_dir: Path) -> None:
    for name in (RSA_KEY_FILENAME, SYMMETRIC_KEY_FILENAME):
        (target_dir / name).unlink(missing_ok=True)
