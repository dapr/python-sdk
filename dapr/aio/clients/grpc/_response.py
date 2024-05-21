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

from typing import AsyncGenerator, Generic

from dapr.proto import api_v1
from dapr.clients.grpc._response import DaprResponse, TCryptoResponse


class CryptoResponse(DaprResponse, Generic[TCryptoResponse]):
    """An asynchronous iterable of cryptography API responses."""

    def __init__(self, stream: AsyncGenerator[TCryptoResponse, None]):
        """Initialize a CryptoResponse.

        Args:
            stream (AsyncGenerator[TCryptoResponse, None, None]): A stream of cryptography API responses.
        """
        self._stream = stream
        self._buffer = bytearray()
        self._expected_seq = 0

    async def __aiter__(self) -> AsyncGenerator[bytes, None]:
        """Read the next chunk of data from the stream.

        Yields:
            bytes: The payload data of the next chunk from the stream.

        Raises:
            ValueError: If the sequence number of the next chunk is incorrect.
        """
        async for chunk in self._stream:
            if chunk.payload.seq != self._expected_seq:
                raise ValueError('invalid sequence number in chunk')
            self._expected_seq += 1
            yield chunk.payload.data

    async def read(self, size: int = -1) -> bytes:
        """Read bytes from the stream.

        If size is -1, the entire stream is read and returned as bytes.
        Otherwise, up to `size` bytes are read from the stream and returned.
        If the stream ends before `size` bytes are available, the remaining
        bytes are returned.

        Args:
            size (int): The maximum number of bytes to read. If -1 (the default),
                read until the end of the stream.

        Returns:
            bytes: The bytes read from the stream.
        """
        if size == -1:
            # Read the entire stream
            return b''.join([chunk async for chunk in self])

        # Read the requested number of bytes
        data = bytes(self._buffer)
        self._buffer.clear()

        async for chunk in self:
            data += chunk
            if len(data) >= size:
                break

        # Update the buffer
        remaining = data[size:]
        self._buffer.extend(remaining)

        # Return the requested number of bytes
        return data[:size]


class EncryptResponse(CryptoResponse[api_v1.EncryptResponse]):
    ...


class DecryptResponse(CryptoResponse[api_v1.DecryptResponse]):
    ...
