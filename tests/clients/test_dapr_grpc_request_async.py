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

import io
import unittest

from dapr.clients.grpc._crypto import EncryptOptions, DecryptOptions
from dapr.aio.clients.grpc._request import EncryptRequestIterator, DecryptRequestIterator
from dapr.proto import api_v1


class EncryptRequestIteratorAsyncTests(unittest.IsolatedAsyncioTestCase):
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
        with self.assertRaises(StopAsyncIteration):
            await req_iter.__anext__()

    async def test_encrypt_request_iterator_empty_data(self):
        # arrange
        encrypt_options = EncryptOptions(
            component_name='crypto_component', key_name='crypto_key', key_wrap_algorithm='RSA'
        )

        # act
        req_iter = EncryptRequestIterator(
            data='',
            options=encrypt_options,
        )

        # assert
        with self.assertRaises(StopAsyncIteration):
            await req_iter.__anext__()

    async def test_encrypt_request_iterator_large_data(self):
        # arrange
        buffer = io.BytesIO()
        for _ in range(100):
            buffer.write(b'a' * 2048)

        encrypt_options = EncryptOptions(
            component_name='crypto_component', key_name='crypto_key', key_wrap_algorithm='RSA'
        )

        # act
        req_iter = EncryptRequestIterator(
            data=buffer.read(),
            options=encrypt_options,
        )

        # assert
        for seq, req in enumerate([req async for req in req_iter]):
            self.assertEqual(req.__class__, api_v1.EncryptRequest)
            self.assertEqual(req.payload.data, b'a')
            self.assertEqual(req.payload.seq, seq)
        with self.assertRaises(StopAsyncIteration):
            await req_iter.__anext__()


class DecryptRequestIteratorAsyncTests(unittest.IsolatedAsyncioTestCase):
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
        with self.assertRaises(StopAsyncIteration):
            await req_iter.__anext__()

    async def test_decrypt_request_iterator_empty_data(self):
        # arrange
        decrypt_options = DecryptOptions(
            component_name='crypto_component',
        )

        # act
        req_iter = DecryptRequestIterator(
            data='',
            options=decrypt_options,
        )

        # assert
        with self.assertRaises(StopAsyncIteration):
            await req_iter.__anext__()

    async def test_decrypt_request_iterator_large_data(self):
        # arrange
        buffer = io.BytesIO()
        for _ in range(100):
            buffer.write(b'a' * 2048)

        decrypt_options = DecryptOptions(
            component_name='crypto_component',
        )

        # act
        req_iter = DecryptRequestIterator(
            data=buffer.read(),
            options=decrypt_options,
        )

        # assert
        for seq, req in enumerate([req async for req in req_iter]):
            self.assertEqual(req.__class__, api_v1.EncryptRequest)
            self.assertEqual(req.payload.data, b'a')
            self.assertEqual(req.payload.seq, seq)
        with self.assertRaises(StopAsyncIteration):
            await req_iter.__anext__()


if __name__ == '__main__':
    unittest.main()
