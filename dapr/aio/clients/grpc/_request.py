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
from typing import Union

from dapr.clients.grpc._crypto import EncryptOptions, DecryptOptions
from dapr.clients.grpc._helpers import to_bytes
from dapr.clients.grpc._request import DaprRequest
from dapr.proto import api_v1, common_v1


class EncryptRequestIterator(DaprRequest):
    """An asynchronous iterator for cryptography encrypt API requests.

    This reads data from a given stream by chunks and converts it to an asynchronous iterator
    of cryptography encrypt API requests.
    This iterator will be used for encrypt gRPC bidirectional streaming requests.
    """

    def __init__(
        self,
        data: Union[str, bytes],
        options: EncryptOptions,
    ):
        """Initialize EncryptRequestIterator with data and encryption options.

        Args:
            data (Union[str, bytes]): data to be encrypted
            options (EncryptOptions): encryption options
        """
        self.data = io.BytesIO(to_bytes(data))
        self.options = options.get_proto()
        self.buffer_size = 2 << 10  # 2KiB
        self.seq = 0

    def __aiter__(self):
        """Returns the iterator object itself."""
        return self

    async def __anext__(self):
        """Read the next chunk of data from the input stream and create a gRPC stream request."""
        # Read data from the input stream, in chunks of up to 2KiB
        # Send the data until we reach the end of the input stream
        chunk = self.data.read(self.buffer_size)
        if not chunk:
            raise StopAsyncIteration

        payload = common_v1.StreamPayload(data=chunk, seq=self.seq)
        if self.seq == 0:
            # If this is the first chunk, add the options
            request_proto = api_v1.EncryptRequest(payload=payload, options=self.options)
        else:
            request_proto = api_v1.EncryptRequest(payload=payload)

        self.seq += 1
        return request_proto


class DecryptRequestIterator(DaprRequest):
    """An asynchronous iterator for cryptography decrypt API requests.

    This reads data from a given stream by chunks and converts it to an asynchronous iterator
    of cryptography decrypt API requests.
    This iterator will be used for encrypt gRPC bidirectional streaming requests.
    """

    def __init__(
        self,
        data: Union[str, bytes],
        options: DecryptOptions,
    ):
        """Initialize DecryptRequestIterator with data and decryption options.

        Args:
            data (Union[str, bytes]): data to be decrypted
            options (DecryptOptions): decryption options
        """
        self.data = io.BytesIO(to_bytes(data))
        self.options = options.get_proto()
        self.buffer_size = 2 << 10  # 2KiB
        self.seq = 0

    def __aiter__(self):
        """Returns the iterator object itself."""
        return self

    async def __anext__(self):
        """Read the next chunk of data from the input stream and create a gRPC stream request."""
        # Read data from the input stream, in chunks of up to 2KiB
        # Send the data until we reach the end of the input stream
        chunk = self.data.read(self.buffer_size)
        if not chunk:
            raise StopAsyncIteration

        payload = common_v1.StreamPayload(data=chunk, seq=self.seq)
        if self.seq == 0:
            # If this is the first chunk, add the options
            request_proto = api_v1.DecryptRequest(payload=payload, options=self.options)
        else:
            request_proto = api_v1.DecryptRequest(payload=payload)

        self.seq += 1
        return request_proto
