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

import io
import operator
import threading
from typing import Any, BinaryIO, Iterator, Optional, Union

from grpc import RpcError  # type: ignore

from dapr.clients.exceptions import DaprGrpcError
from dapr.clients.grpc._helpers import validateNotBlankString
from dapr.conf import settings
from dapr.proto import common_v1
from dapr.proto.runtime.v1 import binarystore_pb2 as binary_v1

DEFAULT_CHUNK_SIZE = 32 * 1024


def validate_names(store_name: str, file_name: str) -> None:
    for name, value in (('store_name', store_name), ('file_name', file_name)):
        if not isinstance(value, str):
            raise TypeError(f'{name} must be a string')
    validateNotBlankString(store_name=store_name, file_name=file_name)


def resolve_timeout(timeout: Optional[float]) -> Optional[float]:
    if timeout is not None:
        return timeout
    configured = settings.DAPR_API_TIMEOUT_SECONDS
    return float(configured) if configured is not None else None


class _BinaryFileUpload:
    """A bounded, single-use upload source. The caller retains ownership of its reader."""

    def __init__(
        self,
        store_name: str,
        file_name: str,
        data: Union[bytes, BinaryIO],
        overwrite: bool,
        chunk_size: int,
    ) -> None:
        validate_names(store_name, file_name)
        if not isinstance(overwrite, bool):
            raise TypeError('overwrite must be a bool')
        if not isinstance(chunk_size, int) or isinstance(chunk_size, bool):
            raise TypeError('chunk_size must be an integer')
        if chunk_size <= 0:
            raise ValueError('chunk_size must be positive')
        if isinstance(data, io.TextIOBase) or (
            not isinstance(data, bytes) and not callable(getattr(data, 'read', None))
        ):
            raise TypeError('data must be bytes or a binary file-like reader')
        self.initial = binary_v1.SetBinaryFileRequestAlpha1(
            initial_request=binary_v1.SetBinaryFileRequestInitialAlpha1(
                component_name=store_name, file_name=file_name, overwrite=overwrite
            )
        )
        self.data = data
        self.chunk_size = chunk_size
        self.error: Optional[Exception] = None
        self._offset = 0
        self._stopped = threading.Event()

    def stop(self) -> None:
        self._stopped.set()

    def read(self) -> bytes:
        if self._stopped.is_set():
            return b''
        if isinstance(self.data, bytes):
            chunk = self.data[self._offset : self._offset + self.chunk_size]
            self._offset += len(chunk)
        else:
            chunk = self.data.read(self.chunk_size)
        if not isinstance(chunk, bytes):
            raise TypeError('binary upload reader must return bytes')
        if len(chunk) > self.chunk_size:
            raise ValueError('binary upload reader returned more than chunk_size bytes')
        return chunk

    def __iter__(self) -> Iterator[binary_v1.SetBinaryFileRequestAlpha1]:
        yield self.initial
        seq = 0
        try:
            while not self._stopped.is_set():
                chunk = self.read()
                if not chunk or self._stopped.is_set():
                    return
                yield binary_v1.SetBinaryFileRequestAlpha1(
                    payload=common_v1.StreamPayload(data=chunk, seq=seq)
                )
                seq += 1
        except Exception as error:
            self.error = error
            raise


class BinaryFileResponse:
    """A single-consumer binary download supporting iteration and file-style reads.

    Use a context manager, or call :meth:`close`, when stopping before EOF. Closing this
    response cancels its RPC, not the client. ``read()`` buffers the remaining file;
    iteration or bounded reads avoid buffering the complete file.
    """

    def __init__(self, stream: Any) -> None:
        self._stream = stream
        self._iterator = iter(stream)
        self._buffer = b''
        self._expected_seq = 0
        self._closed = False
        self._eof = False

    def _check_open(self) -> None:
        if self._closed:
            raise ValueError('I/O operation on closed binary file response')

    def __iter__(self) -> Iterator[bytes]:
        return self

    def __next__(self) -> bytes:
        self._check_open()
        if self._buffer:
            chunk, self._buffer = self._buffer, b''
            return chunk
        if self._eof:
            raise StopIteration
        try:
            while True:
                message = next(self._iterator)
                if not message.HasField('payload'):
                    raise ValueError('binary store response is missing its payload')
                if message.payload.seq != self._expected_seq:
                    raise ValueError('invalid sequence number in binary store response')
                self._expected_seq += 1
                if message.payload.data:
                    return message.payload.data
        except StopIteration:
            self._eof = True
            raise
        except RpcError as error:
            self.close()
            raise DaprGrpcError(error) from error
        except BaseException:
            self.close()
            raise

    def read(self, size: int = -1) -> bytes:
        """Read up to size bytes; a negative size reads the remaining file into memory."""
        self._check_open()
        size = operator.index(size)
        if size < 0:
            return b''.join(self)
        pieces = []
        remaining = size
        while remaining:
            try:
                chunk = next(self)
            except StopIteration:
                break
            pieces.append(chunk[:remaining])
            self._buffer = chunk[remaining:]
            remaining -= min(remaining, len(chunk))
        return b''.join(pieces)

    def close(self) -> None:
        """Cancel an unfinished download. Repeated close calls are harmless."""
        if not self._closed:
            self._closed = True
            self._buffer = b''
            if not self._eof:
                cancel = getattr(self._stream, 'cancel', None)
                if cancel is not None:
                    cancel()
                else:
                    # Some tracing interceptors return a generator instead of
                    # a grpc.Call. Close it to release the underlying stream.
                    close = getattr(self._iterator, 'close', None)
                    if close is not None:
                        close()

    def __enter__(self) -> 'BinaryFileResponse':
        self._check_open()
        return self

    def __exit__(self, exc_type: Any, exc_value: Any, traceback: Any) -> None:
        self.close()
