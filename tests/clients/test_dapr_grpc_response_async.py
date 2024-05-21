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

from dapr.aio.clients.grpc._response import EncryptResponse, DecryptResponse
from dapr.proto import api_v1, common_v1


class CryptoResponseAsyncTests(unittest.IsolatedAsyncioTestCase):
    async def response_stream(self):
        stream1 = common_v1.StreamPayload(data=b'hello', seq=0)
        stream2 = common_v1.StreamPayload(data=b' dapr', seq=1)
        for strm in (stream1, stream2):
            yield api_v1.EncryptResponse(payload=strm)

    async def test_encrypt_response_read_bytes(self):
        resp = EncryptResponse(stream=self.response_stream())
        self.assertEqual(await resp.read(5), b'hello')
        self.assertEqual(await resp.read(5), b' dapr')

    async def test_encrypt_response_read_all(self):
        resp = EncryptResponse(stream=self.response_stream())
        self.assertEqual(await resp.read(), b'hello dapr')

    async def test_decrypt_response_read_bytes(self):
        resp = DecryptResponse(stream=self.response_stream())
        self.assertEqual(await resp.read(5), b'hello')
        self.assertEqual(await resp.read(5), b' dapr')

    async def test_decrypt_response_read_all(self):
        resp = DecryptResponse(stream=self.response_stream())
        self.assertEqual(await resp.read(), b'hello dapr')


if __name__ == '__main__':
    unittest.main()
