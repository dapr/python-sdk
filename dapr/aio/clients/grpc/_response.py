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

import asyncio
import contextlib
import inspect
import logging
import time
from typing import (
    AsyncGenerator,
    Awaitable,
    Callable,
    Dict,
    Generic,
    List,
    Optional,
    Text,
    Union,
)

from dapr.clients.grpc._response import (
    CONFIG_SUBSCRIBE_TIMEOUT_SECONDS,
    ConfigurationResponse,
    DaprResponse,
    TCryptoResponse,
    cancel_config_call,
    config_reconnect_delay,
    config_stream_was_stable,
    describe_config_error,
    is_retryable_config_error,
)
from dapr.proto import api_service_v1, api_v1

logger = logging.getLogger(__name__)

# A configuration handler for the async client: a plain function or an ``async def``.
AsyncConfigurationHandler = Callable[[Text, ConfigurationResponse], Union[None, Awaitable[None]]]


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


class EncryptResponse(CryptoResponse[api_v1.EncryptResponse]): ...


class DecryptResponse(CryptoResponse[api_v1.DecryptResponse]): ...


class AsyncConfigurationWatcher:
    """Reads a SubscribeConfigurationAlpha1 stream in an asyncio task and calls the handler
    for every update.

    This is the asyncio counterpart of ConfigurationWatcher and follows the same rules: it
    re-subscribes with exponential backoff when the stream fails or is closed by the sidecar,
    until stop() is called or a non-retryable error is returned (see
    is_retryable_config_error). ``subscription_id`` is the id of the first stream and is what
    the handler receives; ``id`` is the id of the current stream.

    After each reconnect (not after the first subscribe) the watcher reads the current values
    of the keys with GetConfiguration and passes them to the handler, if there are any, so
    changes made while the stream was down are delivered. This may repeat values that did not
    change. If the read fails, a warning is logged and the subscription carries on.

    ``on_exit`` is called with the watcher when its task exits, whether it was stopped or gave
    up on its own.
    """

    def __init__(
        self, on_exit: Optional[Callable[['AsyncConfigurationWatcher'], None]] = None
    ) -> None:
        self.store_name: Optional[str] = None
        self.keys: Optional[List[str]] = None
        self.id: str = ''
        self.subscription_id: str = ''
        self._ready = asyncio.Event()
        self._stopping = False
        self._call = None
        self._task: Optional[asyncio.Task] = None
        self._stream_established = False
        self._established_at = 0.0
        self._on_exit = on_exit
        self._exited = False

    async def watch_configuration(
        self,
        stub: api_service_v1.DaprStub,
        store_name: str,
        keys: List[str],
        handler: AsyncConfigurationHandler,
        config_metadata: Optional[Dict[str, str]] = None,
    ):
        """Starts the watcher task and returns the subscription id, or None if the sidecar did
        not return one within CONFIG_SUBSCRIBE_TIMEOUT_SECONDS or rejected the subscription."""
        req = api_v1.SubscribeConfigurationRequest(
            store_name=store_name, keys=keys, metadata=config_metadata or {}
        )
        self.keys = keys
        self.store_name = store_name
        self._task = asyncio.create_task(
            self._read_subscribe_config(stub, req, handler),
            name=f'dapr-configuration-watcher-{store_name}',
        )
        try:
            await asyncio.wait_for(self._ready.wait(), timeout=CONFIG_SUBSCRIBE_TIMEOUT_SECONDS)
        except asyncio.TimeoutError:
            logger.warning(
                'Unable to get configuration subscription id for keys %s on store %s',
                self.keys,
                self.store_name,
            )
        if not self.subscription_id:
            await self.stop()
            return None
        return self.subscription_id

    @property
    def stopped(self) -> bool:
        return self._stopping

    @property
    def exited(self) -> bool:
        """True once the watcher task has finished (stopped or gave up)."""
        return self._exited

    def live_stream_id(self) -> Optional[str]:
        """Returns the id of the current stream if one is open and the sidecar has sent its id,
        or None while the watcher is between streams (for example waiting to reconnect)."""
        if self._call is not None and self._stream_established:
            return self.id
        return None

    def request_stop(self) -> None:
        """Marks the watcher as stopping so it does not reconnect when the stream ends."""
        self._stopping = True

    async def stop(self) -> None:
        """Stops reconnecting, cancels the current stream and waits for the task to exit."""
        self._stopping = True
        cancel_config_call(self._call)
        task = self._task
        if task is None or task.done() or task is asyncio.current_task():
            return
        task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await task

    async def _read_subscribe_config(
        self,
        stub: api_service_v1.DaprStub,
        req: api_v1.SubscribeConfigurationRequest,
        handler: AsyncConfigurationHandler,
    ) -> None:
        attempt = 0
        outage_reported = False
        try:
            while not self._stopping:
                self._stream_established = False
                try:
                    await self._consume_stream(stub, req, handler)
                    if not self._stopping:
                        logger.info(
                            'Configuration subscription stream for keys %s on store %s was '
                            'closed by the sidecar, reconnecting',
                            self.keys,
                            self.store_name,
                        )
                except asyncio.CancelledError:
                    raise
                except Exception as error:
                    if self._stopping:
                        break
                    if not is_retryable_config_error(error, established=bool(self.subscription_id)):
                        logger.error(
                            'Configuration subscription for keys %s on store %s stopped: %s',
                            self.keys,
                            self.store_name,
                            describe_config_error(error),
                        )
                        break
                    # Warn once per outage; the retries after that go to DEBUG until a new
                    # stream is up, which is logged at INFO.
                    first_failure = self._stream_established or not outage_reported
                    logger.log(
                        logging.WARNING if first_failure else logging.DEBUG,
                        'Configuration subscription stream for keys %s on store %s failed, '
                        'reconnecting: %s',
                        self.keys,
                        self.store_name,
                        describe_config_error(error),
                    )
                    outage_reported = True
                finally:
                    self._call = None
                if self._stopping:
                    break
                if self._stream_established and config_stream_was_stable(self._established_at):
                    attempt = 0
                delay = config_reconnect_delay(attempt)
                attempt += 1
                await self._wait_before_retry(delay)
        finally:
            self._exited = True
            # Unblock watch_configuration if the first stream never delivered an id.
            self._ready.set()
            logger.debug(
                'Configuration watcher for keys %s on store %s exited', self.keys, self.store_name
            )
            if self._on_exit is not None:
                try:
                    self._on_exit(self)
                except Exception:
                    logger.exception('Configuration watcher exit callback raised an exception')

    async def _consume_stream(
        self,
        stub: api_service_v1.DaprStub,
        req: api_v1.SubscribeConfigurationRequest,
        handler: AsyncConfigurationHandler,
    ) -> None:
        call = stub.SubscribeConfigurationAlpha1(req)
        if self._stopping:
            # stop() was requested while the call was being created.
            cancel_config_call(call)
            return
        self._call = call
        async for response in call:
            if not self._stream_established:
                reconnected = self._on_stream_established(response.id)
                if reconnected and not self._stopping:
                    await self._deliver_current_values(stub, req, handler)
            if self._stopping:
                return
            if len(response.items) > 0:
                await self._deliver(handler, ConfigurationResponse(response.items))

    def _on_stream_established(self, server_id: str) -> bool:
        """Records the id of a new stream. Returns True if it replaces an earlier stream."""
        self.id = server_id
        reconnected = bool(self.subscription_id)
        if not reconnected:
            self.subscription_id = server_id
        else:
            logger.info(
                'Configuration subscription %s for keys %s on store %s reconnected with new id %s',
                self.subscription_id,
                self.keys,
                self.store_name,
                server_id,
            )
        self._established_at = time.monotonic()
        self._stream_established = True
        self._ready.set()
        return reconnected

    async def _deliver_current_values(
        self,
        stub: api_service_v1.DaprStub,
        req: api_v1.SubscribeConfigurationRequest,
        handler: AsyncConfigurationHandler,
    ) -> None:
        """Reads the current values of the subscribed keys and passes them to the handler, so
        changes made while the stream was down are not lost."""
        get_req = api_v1.GetConfigurationRequest(
            store_name=req.store_name, keys=req.keys, metadata=req.metadata
        )
        try:
            response = await stub.GetConfiguration(
                get_req, timeout=CONFIG_SUBSCRIBE_TIMEOUT_SECONDS
            )
        except asyncio.CancelledError:
            raise
        except Exception as error:
            if not self._stopping:
                logger.warning(
                    'Could not read the current configuration for keys %s on store %s after '
                    'reconnecting; changes made while the stream was down may be missed: %s',
                    self.keys,
                    self.store_name,
                    describe_config_error(error),
                )
            return
        if len(response.items) > 0 and not self._stopping:
            await self._deliver(handler, ConfigurationResponse(response.items))

    async def _deliver(
        self,
        handler: AsyncConfigurationHandler,
        response: ConfigurationResponse,
    ) -> None:
        # Accept both plain functions and ``async def`` handlers.
        try:
            result = handler(self.subscription_id, response)
            if inspect.isawaitable(result):
                await result
        except Exception:
            logger.exception(
                'Configuration handler for keys %s on store %s raised an exception',
                self.keys,
                self.store_name,
            )

    async def _wait_before_retry(self, delay: float) -> None:
        await asyncio.sleep(delay)
