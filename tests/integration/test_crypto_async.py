import pytest

from dapr.aio.clients import DaprClient as AsyncDaprClient
from dapr.clients.grpc._crypto import DecryptOptions, EncryptOptions

GRPC_ADDRESS = '127.0.0.1:50001'
CRYPTO_COMPONENT = 'cryptostore'
RSA_KEY = 'rsa-private-key.pem'
SYMMETRIC_KEY = 'symmetric-key-256'

# The crypto API re-emits the alpha warnings on every test run.
pytestmark = pytest.mark.filterwarnings('ignore::UserWarning')


@pytest.fixture(scope='module')
def sidecar(dapr_env):
    dapr_env.start_sidecar(app_id='test-crypto-async')


async def test_rsa_round_trip(sidecar):
    plaintext = b'async crypto secret'

    async with AsyncDaprClient(address=GRPC_ADDRESS) as d:
        encrypted_stream = await d.encrypt(
            data=plaintext,
            options=EncryptOptions(
                component_name=CRYPTO_COMPONENT,
                key_name=RSA_KEY,
                key_wrap_algorithm='RSA',
            ),
        )
        encrypted = await encrypted_stream.read()

        decrypted_stream = await d.decrypt(
            data=encrypted,
            options=DecryptOptions(component_name=CRYPTO_COMPONENT, key_name=RSA_KEY),
        )
        decrypted = await decrypted_stream.read()

    assert decrypted == plaintext


async def test_aes_round_trip(sidecar):
    plaintext = b'A' * (32 * 1024)

    async with AsyncDaprClient(address=GRPC_ADDRESS) as d:
        encrypted_stream = await d.encrypt(
            data=plaintext,
            options=EncryptOptions(
                component_name=CRYPTO_COMPONENT,
                key_name=SYMMETRIC_KEY,
                key_wrap_algorithm='AES',
            ),
        )
        encrypted = await encrypted_stream.read()

        decrypted_stream = await d.decrypt(
            data=encrypted,
            options=DecryptOptions(component_name=CRYPTO_COMPONENT, key_name=SYMMETRIC_KEY),
        )
        decrypted = await decrypted_stream.read()

    assert decrypted == plaintext
