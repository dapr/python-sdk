import pytest

from dapr.clients.grpc._crypto import DecryptOptions, EncryptOptions

# The crypto API re-emits the alpha warnings on every test run.
pytestmark = pytest.mark.filterwarnings('ignore::UserWarning')

CRYPTO_COMPONENT = 'cryptostore'
RSA_KEY = 'rsa-private-key.pem'
SYMMETRIC_KEY = 'symmetric-key-256'


@pytest.fixture(scope='module')
def client(dapr_env):
    return dapr_env.start_sidecar(app_id='test-crypto')


def test_rsa_round_trip(client):
    plaintext = b'The secret is "passw0rd"'

    encrypted = client.encrypt(
        data=plaintext,
        options=EncryptOptions(
            component_name=CRYPTO_COMPONENT,
            key_name=RSA_KEY,
            key_wrap_algorithm='RSA',
        ),
    ).read()
    assert encrypted != plaintext
    assert len(encrypted) > 0

    decrypted = client.decrypt(
        data=encrypted,
        options=DecryptOptions(
            component_name=CRYPTO_COMPONENT,
            key_name=RSA_KEY,
        ),
    ).read()

    assert decrypted == plaintext


def test_aes_round_trip_on_large_payload(client):
    plaintext = b'A' * (64 * 1024)

    encrypted = client.encrypt(
        data=plaintext,
        options=EncryptOptions(
            component_name=CRYPTO_COMPONENT,
            key_name=SYMMETRIC_KEY,
            key_wrap_algorithm='AES',
        ),
    ).read()
    assert encrypted != plaintext

    decrypted = client.decrypt(
        data=encrypted,
        options=DecryptOptions(
            component_name=CRYPTO_COMPONENT,
            key_name=SYMMETRIC_KEY,
        ),
    ).read()

    assert decrypted == plaintext


def test_string_input_round_trip(client):
    message = 'hello dapr'

    encrypted = client.encrypt(
        data=message,
        options=EncryptOptions(
            component_name=CRYPTO_COMPONENT,
            key_name=RSA_KEY,
            key_wrap_algorithm='RSA',
        ),
    ).read()

    decrypted = client.decrypt(
        data=encrypted,
        options=DecryptOptions(
            component_name=CRYPTO_COMPONENT,
            key_name=RSA_KEY,
        ),
    ).read()

    assert decrypted.decode() == message


def test_encrypt_with_empty_component_raises(client):
    with pytest.raises(ValueError):
        client.encrypt(
            data=b'x',
            options=EncryptOptions(
                component_name='',
                key_name=RSA_KEY,
                key_wrap_algorithm='RSA',
            ),
        )


def test_decrypt_with_empty_component_raises(client):
    with pytest.raises(ValueError):
        client.decrypt(
            data=b'x',
            options=DecryptOptions(component_name='', key_name=RSA_KEY),
        )
