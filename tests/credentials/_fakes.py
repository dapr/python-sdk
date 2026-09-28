import time
from datetime import datetime, timedelta, timezone
from typing import Callable, Optional

from dapr.credentials.base import CredentialProvider, WorkloadCredential

POLL_TIMEOUT_SECONDS = 2.0
POLL_INTERVAL_SECONDS = 0.02


def make_credential(token: str, ttl: Optional[timedelta]) -> WorkloadCredential:
    expires_at = datetime.now(timezone.utc) + ttl if ttl is not None else None
    return WorkloadCredential(token=token, expires_at=expires_at)


class FakeProvider(CredentialProvider):
    """Returns token-1, token-2, ... on successive fetches."""

    def __init__(self, ttl: Optional[timedelta] = None):
        self.ttl = ttl
        self.fetch_count = 0
        self.raise_on_next_fetch = False

    def fetch(self) -> WorkloadCredential:
        self.fetch_count += 1
        if self.raise_on_next_fetch:
            self.raise_on_next_fetch = False
            raise RuntimeError('simulated fetch failure')
        return make_credential(f'token-{self.fetch_count}', self.ttl)


def poll_until(predicate: Callable[[], bool]) -> bool:
    deadline = time.monotonic() + POLL_TIMEOUT_SECONDS
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(POLL_INTERVAL_SECONDS)
    return predicate()
