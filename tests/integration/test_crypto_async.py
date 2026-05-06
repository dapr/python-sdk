# -*- coding: utf-8 -*-

"""
Copyright 2026 The Dapr Authors
Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at
    http://www.apache.org/licenses/LICENSE-2.0
Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
"""

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
def sidecar(dapr_env, crypto_keys):
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
