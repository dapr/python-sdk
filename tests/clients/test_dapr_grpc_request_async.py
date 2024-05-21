# -*- coding: utf-8 -*-

"""
Copyright 2023 The Dapr Authors
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

import unittest

from dapr.clients.grpc._crypto import EncryptOptions, DecryptOptions
from dapr.aio.clients.grpc._request import EncryptRequestIterator, DecryptRequestIterator
from dapr.proto import api_v1


class CryptoRequestIteratorAsyncTests(unittest.IsolatedAsyncioTestCase):
    async def test_encrypt_request_iterator(self):
        # arrange
        encrypt_options = EncryptOptions(
            component_name='crypto_component', key_name='crypto_key', key_wrap_algorithm='RSA'
        )

        # act
        req_iter = EncryptRequestIterator(
            data='hello dapr',
            options=encrypt_options,
        )
        req = await req_iter.__anext__()

        # assert
        self.assertEqual(req.__class__, api_v1.EncryptRequest)
        self.assertEqual(req.payload.data, b'hello dapr')
        self.assertEqual(req.payload.seq, 0)

    async def test_decrypt_request_iterator(self):
        # arrange
        decrypt_options = DecryptOptions(
            component_name='crypto_component',
        )

        # act
        req_iter = DecryptRequestIterator(
            data='hello dapr',
            options=decrypt_options,
        )
        req = await req_iter.__anext__()

        # assert
        self.assertEqual(req.__class__, api_v1.DecryptRequest)
        self.assertEqual(req.payload.data, b'hello dapr')
        self.assertEqual(req.payload.seq, 0)


if __name__ == '__main__':
    unittest.main()
