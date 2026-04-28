import pytest

from dapr.clients.grpc._crypto import DecryptOptions, EncryptOptions

CRYPTO_COMPONENT = 'cryptostore'
RSA_KEY = 'rsa-private-key.pem'
SYMMETRIC_KEY = 'symmetric-key-256'

# The crypto API re-emits the alpha warnings on every test run.
pytestmark = pytest.mark.filterwarnings('ignore::UserWarning')


@pytest.fixture(scope='module')
def client(dapr_env, crypto_keys):
    return dapr_env.start_sidecar(app_id='test-crypto')


def test_rsa_round_trip(client):
    plaintext = b'sync crypto secret'

    encrypted_stream = client.encrypt(
        data=plaintext,
        options=EncryptOptions(
            component_name=CRYPTO_COMPONENT,
            key_name=RSA_KEY,
            key_wrap_algorithm='RSA',
        ),
    )
    encrypted = encrypted_stream.read()
    assert encrypted != plaintext

    decrypted_stream = client.decrypt(
        data=encrypted,
        options=DecryptOptions(component_name=CRYPTO_COMPONENT, key_name=RSA_KEY),
    )
    assert decrypted_stream.read() == plaintext


def test_aes_round_trip(client):
    plaintext = b'A' * (32 * 1024)

    encrypted_stream = client.encrypt(
        data=plaintext,
        options=EncryptOptions(
            component_name=CRYPTO_COMPONENT,
            key_name=SYMMETRIC_KEY,
            key_wrap_algorithm='AES',
        ),
    )
    encrypted = encrypted_stream.read()

    decrypted_stream = client.decrypt(
        data=encrypted,
        options=DecryptOptions(component_name=CRYPTO_COMPONENT, key_name=SYMMETRIC_KEY),
    )
    assert decrypted_stream.read() == plaintext


def test_string_input_round_trip(client):
    plaintext = 'hello dapr crypto'

    encrypted_stream = client.encrypt(
        data=plaintext,
        options=EncryptOptions(
            component_name=CRYPTO_COMPONENT,
            key_name=RSA_KEY,
            key_wrap_algorithm='RSA',
        ),
    )
    encrypted = encrypted_stream.read()

    decrypted_stream = client.decrypt(
        data=encrypted,
        options=DecryptOptions(component_name=CRYPTO_COMPONENT, key_name=RSA_KEY),
    )
    assert decrypted_stream.read().decode() == plaintext


def test_encrypt_with_blank_component_raises(client):
    with pytest.raises(ValueError):
        client.encrypt(
            data=b'payload',
            options=EncryptOptions(
                component_name='',
                key_name=RSA_KEY,
                key_wrap_algorithm='RSA',
            ),
        )


def test_decrypt_with_blank_component_raises(client):
    with pytest.raises(ValueError):
        client.decrypt(
            data=b'payload',
            options=DecryptOptions(component_name='', key_name=RSA_KEY),
        )
