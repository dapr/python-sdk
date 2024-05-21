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


class CryptoRequestIterator(DaprRequest):
    """An asynchronous iterator for cryptography API requests.

    This reads data from a given stream by chunks and converts it to an asynchronous iterator
    of cryptography API requests.

    This iterator will be used for encrypt and decrypt gRPC bidirectional streaming requests.
    """

    def __init__(
        self,
        data: Union[str, bytes],
        options: Union[EncryptOptions, DecryptOptions],
        request_type: Union[api_v1.EncryptRequest, api_v1.DecryptRequest],
    ):
        """Initialize CryptoRequestIterator with data and encryption/decryption options.

        Args:
            data (Union[str, bytes]): data to be encrypted or decrypted
            options (Union[EncryptOptions, DecryptOptions]): encryption or decryption options
            request_type (Union[api_v1.EncryptRequest, api_v1.DecryptRequest]): cryptography API request type
        """
        self.data = io.BytesIO(to_bytes(data))
        self.options = options.get_proto()
        self.request_type = request_type
        self.buffer_size = 2 << 10  # 2KiB
        self.seq = 0

    def __aiter__(self):
        """Returns the iterator object itself."""
        return self

    async def __anext__(self):
        """Read the next chunk of data from the input stream and create a gRPC stream request."""
        # Read data from the input stream, in chunks of up to 2KB
        # Send the data until we reach the end of the input stream
        chunk = self.data.read(self.buffer_size)
        if not chunk:
            raise StopAsyncIteration

        payload = common_v1.StreamPayload(data=chunk, seq=self.seq)
        if self.seq == 0:
            # If this is the first chunk, add the options
            request_proto = self.request_type(payload=payload, options=self.options)
        else:
            request_proto = self.request_type(payload=payload)

        self.seq += 1
        return request_proto


class EncryptRequestIterator(CryptoRequestIterator):
    """An asynchronous iterator for encrypt API request.

    This inherits from CryptoRequestIterator.
    """

    def __init__(self, data: Union[str, bytes], options: EncryptOptions):
        """Initialize EncryptRequestIterator with data and options.

        Args:
            data (Union[str, bytes]): data to be encrypted
            options (EncryptOptions): encryption options
        """
        super().__init__(data, options, api_v1.EncryptRequest)


class DecryptRequestIterator(CryptoRequestIterator):
    """An asynchronous iterator for decrypt API requests.

    This inherits from CryptoRequestIterator.
    """

    def __init__(self, data: Union[str, bytes], options: DecryptOptions):
        """Initialize DecryptRequestIterator with data and options.

        Args:
            data (Union[str, bytes]): data to be decrypted
            options (DecryptOptions): decryption options
        """
        super().__init__(data, options, api_v1.DecryptRequest)
