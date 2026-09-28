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
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional


@dataclass(frozen=True)
class WorkloadCredential:
    """A bearer token produced by a :class:`CredentialProvider`.

    Attributes:
        token: The bearer token, e.g. a JWT access token.
        expires_at: Timezone-aware expiry, or ``None`` for a token that never expires.
    """

    token: str
    expires_at: Optional[datetime] = None

    def __post_init__(self) -> None:
        if not self.token:
            raise ValueError('a credential requires a non-empty token')
        if self.expires_at is not None and self.expires_at.tzinfo is None:
            raise ValueError('expires_at must be timezone-aware')

    def is_expired(self, *, now: Optional[datetime] = None) -> bool:
        """Whether this credential is past its expiry. Always ``False`` when it never expires."""
        if self.expires_at is None:
            return False
        current_time = now or datetime.now(timezone.utc)
        return current_time >= self.expires_at


class CredentialProvider(ABC):
    """Produces :class:`WorkloadCredential` instances.

    Providers fetch on every call; caching and refresh scheduling belong to
    :class:`~dapr.credentials.manager.CredentialManager`.
    """

    @abstractmethod
    def fetch(self) -> WorkloadCredential:
        """Fetches the current credential, synchronously."""

    async def fetch_async(self) -> WorkloadCredential:
        """Fetches the current credential. Defaults to running :meth:`fetch` in a thread."""
        return await asyncio.to_thread(self.fetch)
