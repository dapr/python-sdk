"""
Copyright 2025 The Dapr Authors
Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at
    http://www.apache.org/licenses/LICENSE-2.0
Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the specific language governing permissions and
limitations under the License.
"""

from __future__ import annotations

import hashlib
import random
import string as _string
import uuid
from dataclasses import dataclass
from datetime import datetime

"""
Deterministic utilities for async workflows.

Provides replay-stable PRNG and UUID generation seeded from workflow instance
identity and orchestration time.
"""


@dataclass(frozen=True)
class DeterminismSeed:
    instance_id: str
    orchestration_unix_ts: int

    def to_int(self) -> int:
        payload = f'{self.instance_id}:{self.orchestration_unix_ts}'.encode()
        digest = hashlib.sha256(payload).digest()
        # Use first 8 bytes as integer seed to stay within Python int range
        return int.from_bytes(digest[:8], byteorder='big', signed=False)


def derive_seed(instance_id: str, orchestration_time: datetime) -> int:
    ts = int(orchestration_time.timestamp())
    return DeterminismSeed(instance_id=instance_id, orchestration_unix_ts=ts).to_int()


def deterministic_random(instance_id: str, orchestration_time: datetime) -> random.Random:
    seed = derive_seed(instance_id, orchestration_time)
    return random.Random(seed)


def deterministic_uuid4(rnd: random.Random) -> uuid.UUID:
    bytes_ = bytes(rnd.randrange(0, 256) for _ in range(16))
    return uuid.UUID(bytes=bytes_)


class DeterministicContextMixin:
    """
    Mixin providing deterministic helpers for workflow contexts.

    Assumes the inheriting class exposes `instance_id` and `current_utc_datetime` attributes.
    """

    def now(self) -> datetime:
        """Return orchestration time (deterministic current UTC time)."""
        return self.current_utc_datetime  # type: ignore[attr-defined]

    def random(self) -> random.Random:
        """Return a PRNG seeded deterministically from instance id and orchestration time."""
        return deterministic_random(
            self.instance_id,  # type: ignore[attr-defined]
            self.current_utc_datetime,  # type: ignore[attr-defined]
        )

    def uuid4(self) -> uuid.UUID:
        """Return a deterministically generated UUID using the deterministic PRNG."""
        rnd = self.random()
        return deterministic_uuid4(rnd)

    def new_guid(self) -> uuid.UUID:
        """Alias for uuid4 for API parity with other SDKs."""
        return self.uuid4()

    def random_string(self, length: int, *, alphabet: str | None = None) -> str:
        """
        Return a deterministically generated random string of the given length.

        Parameters
        ----------
        length: int
            Desired length of the string. Must be >= 0.
        alphabet: str | None
            Optional set of characters to sample from. Defaults to ASCII letters + digits.
        """
        if length < 0:
            raise ValueError('length must be non-negative')
        chars = alphabet if alphabet is not None else (_string.ascii_letters + _string.digits)
        if not chars:
            raise ValueError('alphabet must not be empty')
        rnd = self.random()
        size = len(chars)
        return ''.join(chars[rnd.randrange(0, size)] for _ in range(length))
