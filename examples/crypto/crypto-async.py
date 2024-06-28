# ------------------------------------------------------------
# Copyright 2021 The Dapr Authors
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#     http://www.apache.org/licenses/LICENSE-2.0
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
# ------------------------------------------------------------

import asyncio

from dapr.aio.clients import DaprClient
from dapr.clients.grpc._crypto import EncryptOptions, DecryptOptions

# Name of the crypto component to use
CRYPTO_COMPONENT_NAME = 'crypto-localstorage'
# Name of the RSA private key to use
RSA_KEY_NAME = 'rsa-private-key.pem'
# Name of the symmetric (AES) key to use
SYMMETRIC_KEY_NAME = 'symmetric-key-256'


async def main():
    print('Running gRPC client asynchronous API')

    async with DaprClient() as dapr:
        # Step 1: encrypt a string using the RSA key, then decrypt it and show the output in the terminal
        print('Running encrypt/decrypt operation on string')
        await encrypt_decrypt_string_async(dapr)

        # Step 2: encrypt a large file and then decrypt it, using the AES key
        print('Running encrypt/decrypt operation on file')
        await encrypt_decrypt_file_async(dapr)


async def encrypt_decrypt_string_async(dapr: DaprClient):
    message = 'The secret is "passw0rd"'

    # Encrypt the message
    resp = await dapr.encrypt(
        data=message.encode(),
        options=EncryptOptions(
            component_name=CRYPTO_COMPONENT_NAME,
            key_name=RSA_KEY_NAME,
            key_wrap_algorithm='RSA',
        ),
    )

    # The method returns a readable stream, which we read in full in memory
    encrypt_bytes = await resp.read()
    print(f'Encrypted the message, got {len(encrypt_bytes)} bytes')

    # Decrypt the encrypted data
    resp = await dapr.decrypt(
        data=encrypt_bytes,
        options=DecryptOptions(
            component_name=CRYPTO_COMPONENT_NAME,
            key_name=RSA_KEY_NAME,
        ),
    )

    # The method returns a readable stream, which we read in full in memory
    decrypt_bytes = await resp.read()
    print(f'Decrypted the message, got {len(decrypt_bytes)} bytes')

    print(decrypt_bytes.decode())
    assert message == decrypt_bytes.decode()


async def encrypt_decrypt_file_async(dapr: DaprClient):
    file_name = 'desert.jpg'

    # Encrypt the file
    with open(file_name, 'r+b') as target_file:
        encrypt_stream = await dapr.encrypt(
            data=target_file.read(),
            options=EncryptOptions(
                component_name=CRYPTO_COMPONENT_NAME,
                key_name=SYMMETRIC_KEY_NAME,
                key_wrap_algorithm='AES',
            ),
        )

    # Write the encrypted data to a file "encrypted.out"
    with open('encrypted.out', 'w+b') as encrypted_file:
        encrypted_file.write(await encrypt_stream.read())
        print('Wrote encrypted data to encrypted.out')

    # Decrypt the encrypted data
    with open('encrypted.out', 'r+b') as encrypted_file:
        decrypt_stream = await dapr.decrypt(
            data=encrypted_file.read(),
            options=DecryptOptions(
                component_name=CRYPTO_COMPONENT_NAME,
                key_name=SYMMETRIC_KEY_NAME,
            ),
        )

    # Write the decrypted data to a file "decrypted.out.jpg"
    with open('decrypted.out.jpg', 'w+b') as decrypted_file:
        decrypted_file.write(await decrypt_stream.read())
        print('Wrote decrypted data to decrypted.out.jpg')


if __name__ == '__main__':
    asyncio.run(main())
