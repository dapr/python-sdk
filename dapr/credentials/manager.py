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
import logging
import threading
from datetime import datetime, timedelta, timezone
from typing import Optional

from dapr.credentials.base import CredentialProvider, WorkloadCredential

logger = logging.getLogger(__name__)

DEFAULT_REFRESH_MARGIN_SECONDS = 60.0
DEFAULT_MIN_REFRESH_INTERVAL_SECONDS = 5.0


def _next_refresh_delay(
    credential: WorkloadCredential,
    refresh_margin: timedelta,
    min_refresh_interval: float,
) -> Optional[float]:
    """Seconds until the next proactive refresh, or None if the credential never expires."""
    if credential.expires_at is None:
        return None
    remaining = (
        credential.expires_at - refresh_margin - datetime.now(timezone.utc)
    ).total_seconds()
    return max(remaining, min_refresh_interval)


class CredentialManager:
    """Caches the credential from a :class:`~dapr.credentials.base.CredentialProvider` and
    refreshes it ahead of expiry. Safe to share across threads.
    """

    def __init__(
        self,
        provider: CredentialProvider,
        *,
        refresh_margin_seconds: float = DEFAULT_REFRESH_MARGIN_SECONDS,
        min_refresh_interval_seconds: float = DEFAULT_MIN_REFRESH_INTERVAL_SECONDS,
    ) -> None:
        """
        Args:
            provider: Fetches the credential.
            refresh_margin_seconds: How long before expiry a background refresh happens.
            min_refresh_interval_seconds: The shortest delay between background refreshes,
                including retries after a failed refresh.
        """
        self._provider = provider
        self._refresh_margin = timedelta(seconds=refresh_margin_seconds)
        self._min_refresh_interval = min_refresh_interval_seconds
        self._lock = threading.Lock()
        self._credential: Optional[WorkloadCredential] = None
        self._refresh_timer: Optional[threading.Timer] = None
        self._started = False
        self._closed = False

    @property
    def provider(self) -> CredentialProvider:
        """The wrapped provider."""
        return self._provider

    @property
    def current(self) -> Optional[WorkloadCredential]:
        """The cached credential, or ``None`` before the first fetch. Never fetches."""
        return self._credential

    def get(self) -> WorkloadCredential:
        """Returns the cached credential, fetching it first if missing or expired."""
        with self._lock:
            if self._credential is None or self._credential.is_expired():
                self._credential = self._provider.fetch()
            return self._credential

    def start(self) -> None:
        """Fetches the credential and schedules background refreshes ahead of expiry.
        Idempotent."""
        if self._started:
            return
        self._started = True
        self.get()
        self._schedule_next_refresh()

    def close(self) -> None:
        """Stops background refreshes. The manager remains usable via :meth:`get`."""
        self._closed = True
        with self._lock:
            if self._refresh_timer is not None:
                self._refresh_timer.cancel()
                self._refresh_timer = None

    def refresh_now(self) -> None:
        """Fetches a new credential, bypassing the cache.

        The fetch runs outside the lock so concurrent :meth:`get` calls keep returning the
        still-valid cached credential instead of blocking on the network.
        """
        credential = self._provider.fetch()
        with self._lock:
            self._credential = credential

    def _schedule_next_refresh(self) -> None:
        # Guards against close() racing a refresh that has already started.
        if self._closed:
            return
        assert self._credential is not None
        delay = _next_refresh_delay(
            self._credential, self._refresh_margin, self._min_refresh_interval
        )
        if delay is None:
            return
        self._refresh_timer = threading.Timer(delay, self._background_refresh)
        self._refresh_timer.daemon = True
        self._refresh_timer.start()

    def _background_refresh(self) -> None:
        if self._closed:
            return
        try:
            self.refresh_now()
        except Exception:
            logger.exception('workload identity credential refresh failed, will retry')
        self._schedule_next_refresh()


class AsyncCredentialManager:
    """Asyncio counterpart of :class:`CredentialManager`, fetching via
    :meth:`CredentialProvider.fetch_async` and refreshing from an ``asyncio`` task.
    """

    def __init__(
        self,
        provider: CredentialProvider,
        *,
        refresh_margin_seconds: float = DEFAULT_REFRESH_MARGIN_SECONDS,
        min_refresh_interval_seconds: float = DEFAULT_MIN_REFRESH_INTERVAL_SECONDS,
    ) -> None:
        """See :class:`CredentialManager`."""
        self._provider = provider
        self._refresh_margin = timedelta(seconds=refresh_margin_seconds)
        self._min_refresh_interval = min_refresh_interval_seconds
        # asyncio.Lock is bound to one loop, but DaprInvocationHttpClient awaits this manager
        # from a new loop per call; _current_lock() rebuilds it when the loop changes.
        self._lock = asyncio.Lock()
        self._lock_loop: Optional[asyncio.AbstractEventLoop] = None
        self._credential: Optional[WorkloadCredential] = None
        self._refresh_task: Optional[asyncio.Task] = None
        self._started = False
        self._closed = False
        try:
            self._loop: Optional[asyncio.AbstractEventLoop] = asyncio.get_running_loop()
        except RuntimeError:
            self._loop = None

    @property
    def provider(self) -> CredentialProvider:
        """The wrapped provider."""
        return self._provider

    @property
    def current(self) -> Optional[WorkloadCredential]:
        """The cached credential, or ``None`` before the first fetch. Never fetches."""
        return self._credential

    @property
    def loop(self) -> Optional[asyncio.AbstractEventLoop]:
        """The loop this manager was created or started on, or ``None`` if neither ran in one."""
        return self._loop

    def ensure_current_loop(self) -> None:
        """Captures the running loop if none was captured at construction."""
        if self._loop is None:
            self._loop = asyncio.get_running_loop()

    async def get(self) -> WorkloadCredential:
        """Returns the cached credential, fetching it first if missing or expired."""
        async with self._current_lock():
            if self._credential is None or self._credential.is_expired():
                self._credential = await self._provider.fetch_async()
            return self._credential

    async def start(self) -> None:
        """Fetches the credential and schedules background refreshes on the running loop.
        Idempotent."""
        if self._started:
            return
        self._started = True
        self._loop = asyncio.get_running_loop()
        await self.get()
        self._schedule_next_refresh()

    async def close(self) -> None:
        """Stops background refreshes. The manager remains usable via :meth:`get`."""
        self._closed = True
        task = self._refresh_task
        self._refresh_task = None
        if task is not None:
            task.cancel()

    async def refresh_now(self) -> None:
        """Fetches a new credential, bypassing the cache.

        The fetch runs outside the lock so concurrent :meth:`get` calls keep returning the
        still-valid cached credential.
        """
        credential = await self._provider.fetch_async()
        async with self._current_lock():
            self._credential = credential

    def _current_lock(self) -> asyncio.Lock:
        loop = asyncio.get_running_loop()
        if self._lock_loop is not loop:
            self._lock = asyncio.Lock()
            self._lock_loop = loop
        return self._lock

    def _schedule_next_refresh(self) -> None:
        # Guards against close() racing a refresh that has already started.
        if self._closed:
            return
        assert self._credential is not None
        delay = _next_refresh_delay(
            self._credential, self._refresh_margin, self._min_refresh_interval
        )
        if delay is None:
            return
        self._refresh_task = asyncio.ensure_future(self._background_refresh(delay))

    async def _background_refresh(self, delay: float) -> None:
        await asyncio.sleep(delay)
        if self._closed:
            return
        try:
            await self.refresh_now()
        except Exception:
            logger.exception('workload identity credential refresh failed, will retry')
        self._schedule_next_refresh()
