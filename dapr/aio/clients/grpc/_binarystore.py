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

import asyncio
import operator
from typing import Any, AsyncIterator, Optional

from grpc import StatusCode  # type: ignore
from grpc.aio import AioRpcError, Metadata  # type: ignore

from dapr.clients.exceptions import DaprGrpcError
from dapr.clients.grpc._binarystore import _BinaryFileUpload
from dapr.proto import common_v1
from dapr.proto.runtime.v1 import binarystore_pb2 as binary_v1


class _AsyncBinaryFileUpload:
    """Pull-based request production with explicit ownership of pending file reads."""

    def __init__(self, source: _BinaryFileUpload) -> None:
        self._source = source
        self._initial_sent = False
        self._seq = 0
        self._closed = False
        self._read_task: Optional[asyncio.Task[bytes]] = None

    def __aiter__(self) -> '_AsyncBinaryFileUpload':
        return self

    async def __anext__(self) -> binary_v1.SetBinaryFileRequestAlpha1:
        if self._closed:
            raise StopAsyncIteration
        if not self._initial_sent:
            self._initial_sent = True
            return self._source.initial
        try:
            if isinstance(self._source.data, bytes):
                chunk = self._source.read()
            else:
                self._read_task = asyncio.create_task(asyncio.to_thread(self._source.read))
                try:
                    chunk = await self._read_task
                finally:
                    self._read_task = None
        except Exception as error:
            # grpc.aio cancels the RPC when a request iterator raises. Retain
            # the actual local error so the client can report it to the caller.
            self._source.error = error
            raise
        if self._closed or not chunk:
            raise StopAsyncIteration
        request = binary_v1.SetBinaryFileRequestAlpha1(
            payload=common_v1.StreamPayload(data=chunk, seq=self._seq)
        )
        self._seq += 1
        return request

    async def aclose(self) -> None:
        self._closed = True
        self._source.stop()
        if self._read_task is not None:
            # This ends the iterator's wait, including after an early server
            # rejection. An already-running thread read cannot be interrupted.
            task = self._read_task
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)


class AsyncBinaryFileResponse:
    """An asynchronous binary download with one cursor for iteration and reads.

    Use ``async with`` or :meth:`aclose` when stopping early. An unbounded ``read()``
    buffers the remaining file; bounded reads and iteration preserve streaming.
    Concurrent reads on the same response are unsupported.
    """

    def __init__(self, stream: Any) -> None:
        self._stream = stream
        self._iterator = stream.__aiter__()
        self._buffer = b''
        self._expected_seq = 0
        self._closed = False
        self._eof = False
        self._read_task: Optional[asyncio.Future[Any]] = None

    def _check_open(self) -> None:
        if self._closed:
            raise ValueError('I/O operation on closed binary file response')

    def __aiter__(self) -> AsyncIterator[bytes]:
        return self

    async def _next_message(self) -> binary_v1.GetBinaryFileResponseAlpha1:
        task = asyncio.ensure_future(self._iterator.__anext__())
        self._read_task = task
        try:
            # wait() raises CancelledError only for cancellation of this reader's
            # task. Inspecting the result separately also works on Python 3.10,
            # where Task.cancelling() is unavailable.
            await asyncio.wait((task,))
            try:
                return task.result()
            except asyncio.CancelledError as error:
                raise AioRpcError(
                    StatusCode.CANCELLED,
                    Metadata(),
                    Metadata(),
                    'Binary file download was cancelled',
                ) from error
        finally:
            if not task.done():
                task.cancel()
                await asyncio.gather(task, return_exceptions=True)
            self._read_task = None

    async def __anext__(self) -> bytes:
        self._check_open()
        if self._buffer:
            chunk, self._buffer = self._buffer, b''
            return chunk
        if self._eof:
            raise StopAsyncIteration
        try:
            while True:
                message = await self._next_message()
                if not message.HasField('payload'):
                    raise ValueError('binary store response is missing its payload')
                if message.payload.seq != self._expected_seq:
                    raise ValueError('invalid sequence number in binary store response')
                self._expected_seq += 1
                if message.payload.data:
                    return message.payload.data
        except StopAsyncIteration:
            self._eof = True
            raise
        except AioRpcError as error:
            await self.aclose()
            raise DaprGrpcError(error) from error
        except BaseException:
            await self.aclose()
            raise

    async def read(self, size: int = -1) -> bytes:
        """Read up to size bytes; a negative size reads the remaining file into memory."""
        self._check_open()
        size = operator.index(size)
        if size < 0:
            return b''.join([chunk async for chunk in self])
        pieces = []
        remaining = size
        while remaining:
            try:
                chunk = await self.__anext__()
            except StopAsyncIteration:
                break
            pieces.append(chunk[:remaining])
            self._buffer = chunk[remaining:]
            remaining -= min(remaining, len(chunk))
        return b''.join(pieces)

    async def aclose(self) -> None:
        """Cancel an unfinished download without closing the client."""
        if not self._closed:
            self._closed = True
            self._buffer = b''
            if not self._eof:
                cancel = getattr(self._stream, 'cancel', None)
                if cancel is not None:
                    cancel()
                else:
                    # A tracing interceptor may expose only an async iterator.
                    # Stop an active read before closing its generator.
                    task = self._read_task
                    if task is not None:
                        task.cancel()
                        await asyncio.gather(task, return_exceptions=True)
                    close = getattr(self._iterator, 'aclose', None)
                    if close is not None:
                        await close()

    async def __aenter__(self) -> 'AsyncBinaryFileResponse':
        self._check_open()
        return self

    async def __aexit__(self, exc_type: Any, exc_value: Any, traceback: Any) -> None:
        await self.aclose()
