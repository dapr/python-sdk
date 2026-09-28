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
from functools import partial
from typing import Any, Callable

import grpc  # type: ignore

from dapr.credentials.manager import AsyncCredentialManager, CredentialManager

DEFAULT_METADATA_KEY = 'dapr-api-token'
DEFAULT_PLUGIN_TIMEOUT_SECONDS = 10.0


class _AuthMetadataPlugin(grpc.AuthMetadataPlugin):
    """Attaches a bearer token to each call. gRPC invokes it per call on its own thread."""

    def __init__(self, get_token: Callable[[], str], metadata_key: str) -> None:
        self._get_token = get_token
        self._metadata_key = metadata_key

    def __call__(self, context: Any, callback: Any) -> None:
        try:
            token = self._get_token()
        except Exception as error:
            callback((), error)
            return
        callback(((self._metadata_key, token),), None)


def build_channel_credentials(
    manager: CredentialManager,
    channel_credentials: grpc.ChannelCredentials,
    *,
    metadata_key: str = DEFAULT_METADATA_KEY,
) -> grpc.ChannelCredentials:
    """Composes TLS ``channel_credentials`` with call credentials carrying ``manager``'s
    token, so a rotated token needs no new channel."""
    plugin = _AuthMetadataPlugin(lambda: manager.get().token, metadata_key)
    call_credentials = grpc.metadata_call_credentials(plugin)
    return grpc.composite_channel_credentials(channel_credentials, call_credentials)


def _async_bearer_token(manager: AsyncCredentialManager, plugin_timeout_seconds: float) -> str:
    # Skip the cross-thread hop while the cached token is valid.
    cached = manager.current
    if cached is not None and not cached.is_expired():
        return cached.token

    loop = manager.loop
    if loop is None:
        raise RuntimeError('AsyncCredentialManager.start() must be awaited before use')
    future = asyncio.run_coroutine_threadsafe(manager.get(), loop)
    return future.result(timeout=plugin_timeout_seconds).token


def build_async_channel_credentials(
    manager: AsyncCredentialManager,
    channel_credentials: grpc.ChannelCredentials,
    *,
    metadata_key: str = DEFAULT_METADATA_KEY,
    plugin_timeout_seconds: float = DEFAULT_PLUGIN_TIMEOUT_SECONDS,
) -> grpc.ChannelCredentials:
    """Async counterpart of :func:`build_channel_credentials`.

    ``manager.loop`` must be set, since refreshes are run on that loop.
    """
    get_token = partial(_async_bearer_token, manager, plugin_timeout_seconds)
    call_credentials = grpc.metadata_call_credentials(_AuthMetadataPlugin(get_token, metadata_key))
    return grpc.composite_channel_credentials(channel_credentials, call_credentials)
