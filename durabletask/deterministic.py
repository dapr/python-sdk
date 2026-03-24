"""
Copyright 2025 The Dapr Authors
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

"""
Deterministic utilities for Durable Task workflows (async and generator).

This module provides deterministic alternatives to non-deterministic Python
functions, ensuring workflow replay consistency across different executions.
It is shared by both the asyncio authoring model and the generator-based model.
"""

import hashlib
import random
import string as _string
import uuid
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Optional, TypeVar


@dataclass
class DeterminismSeed:
    """Seed data for deterministic operations."""

    instance_id: str
    orchestration_unix_ts: int

    def to_int(self) -> int:
        """Convert seed to integer for PRNG initialization."""
        combined = f"{self.instance_id}:{self.orchestration_unix_ts}"
        hash_bytes = hashlib.sha256(combined.encode("utf-8")).digest()
        return int.from_bytes(hash_bytes[:8], byteorder="big")


def derive_seed(instance_id: str, orchestration_time: datetime) -> int:
    """
    Derive a deterministic seed from instance ID and orchestration time.
    """
    ts = int(orchestration_time.timestamp())
    return DeterminismSeed(instance_id=instance_id, orchestration_unix_ts=ts).to_int()


def deterministic_random(instance_id: str, orchestration_time: datetime) -> random.Random:
    """
    Create a deterministic random number generator.
    """
    seed = derive_seed(instance_id, orchestration_time)
    return random.Random(seed)


def deterministic_uuid4(rnd: random.Random) -> uuid.UUID:
    """
    Generate a deterministic UUID4 using the provided random generator.

    Note: This is deprecated in favor of deterministic_uuid_v5 which matches
    the .NET implementation for cross-language compatibility.
    """
    bytes_ = bytes(rnd.randrange(0, 256) for _ in range(16))
    bytes_list = list(bytes_)
    bytes_list[6] = (bytes_list[6] & 0x0F) | 0x40  # Version 4
    bytes_list[8] = (bytes_list[8] & 0x3F) | 0x80  # Variant bits
    return uuid.UUID(bytes=bytes(bytes_list))


def deterministic_uuid_v5(instance_id: str, current_datetime: datetime, counter: int) -> uuid.UUID:
    """
    Generate a deterministic UUID v5 matching the .NET implementation.

    This implementation matches the durabletask-dotnet NewGuid() method:
    https://github.com/microsoft/durabletask-dotnet/blob/main/src/Worker/Core/Shims/TaskOrchestrationContextWrapper.cs

    Args:
        instance_id: The orchestration instance ID.
        current_datetime: The current orchestration datetime (frozen during replay).
        counter: The per-call counter (starts at 0 on each replay).

    Returns:
        A deterministic UUID v5 that will be the same across replays.
    """
    # DNS namespace UUID - same as .NET DnsNamespaceValue
    namespace = uuid.UUID("9e952958-5e33-4daf-827f-2fa12937b875")

    # Build name matching .NET format: instanceId_datetime_counter
    # Using isoformat() which produces ISO 8601 format similar to .NET's ToString("o")
    name = f"{instance_id}_{current_datetime.isoformat()}_{counter}"

    # Generate UUID v5 (SHA-1 based, matching .NET)
    return uuid.uuid5(namespace, name)


class DeterministicContextMixin:
    """
    Mixin providing deterministic helpers for workflow contexts.

    Assumes the inheriting class exposes `instance_id` and `current_utc_datetime` attributes.

    This implementation matches the .NET durabletask SDK approach with an explicit
    counter for UUID generation that resets on each replay.
    """

    def __init__(self, *args, **kwargs):
        """Initialize the mixin with UUID and timestamp counters."""
        super().__init__(*args, **kwargs)
        # Counter for deterministic UUID generation (matches .NET newGuidCounter)
        # This counter resets to 0 on each replay, ensuring determinism
        self._uuid_counter: int = 0
        # Counter for deterministic timestamp sequencing (resets on replay)
        self._timestamp_counter: int = 0

    def now(self) -> datetime:
        """Alias for deterministic current_utc_datetime."""
        return self.current_utc_datetime  # type: ignore[attr-defined]

    def random(self) -> random.Random:
        """Return a PRNG seeded deterministically from instance id and orchestration time."""
        rnd = deterministic_random(
            self.instance_id,  # type: ignore[attr-defined]
            self.current_utc_datetime,  # type: ignore[attr-defined]
        )
        # Mark as deterministic for asyncio sandbox detector whitelisting of bound methods (randint, random)
        try:
            rnd._dt_deterministic = True
        except Exception:
            pass
        return rnd

    def uuid4(self) -> uuid.UUID:
        """
        Return a deterministically generated UUID v5 with explicit counter.
        https://www.sohamkamani.com/uuid-versions-explained/#v5-non-random-uuids

        This matches the .NET implementation's NewGuid() method which uses:
        - Instance ID
        - Current UTC datetime (frozen during replay)
        - Per-call counter (resets to 0 on each replay)

        The counter ensures multiple calls produce different UUIDs while maintaining
        determinism across replays.
        """
        # Lazily initialize counter if not set by __init__ (for compatibility)
        if not hasattr(self, "_uuid_counter"):
            self._uuid_counter = 0

        result = deterministic_uuid_v5(
            self.instance_id,  # type: ignore[attr-defined]
            self.current_utc_datetime,  # type: ignore[attr-defined]
            self._uuid_counter,
        )
        self._uuid_counter += 1
        return result

    def new_guid(self) -> uuid.UUID:
        """Alias for uuid4 for API parity with other SDKs."""
        return self.uuid4()

    def random_string(self, length: int, *, alphabet: Optional[str] = None) -> str:
        """Return a deterministically generated random string of the given length."""
        if length < 0:
            raise ValueError("length must be non-negative")
        chars = alphabet if alphabet is not None else (_string.ascii_letters + _string.digits)
        if not chars:
            raise ValueError("alphabet must not be empty")
        rnd = self.random()
        size = len(chars)
        return "".join(chars[rnd.randrange(0, size)] for _ in range(length))

    def random_int(self, min_value: int = 0, max_value: int = 2**31 - 1) -> int:
        """Return a deterministic random integer in the specified range."""
        if min_value > max_value:
            raise ValueError("min_value must be <= max_value")
        rnd = self.random()
        return rnd.randint(min_value, max_value)

    T = TypeVar("T")

    def random_choice(self, sequence: Sequence[T]) -> T:
        """Return a deterministic random element from a non-empty sequence."""
        if not sequence:
            raise IndexError("Cannot choose from empty sequence")
        rnd = self.random()
        return rnd.choice(sequence)

    def now_with_sequence(self) -> datetime:
        """
        Return deterministic timestamp with microsecond increment per call.

        Each call returns: current_utc_datetime + (counter * 1 microsecond)

        This provides ordered, unique timestamps for tracing/telemetry while maintaining
        determinism across replays. The counter resets to 0 on each replay (similar to
        _uuid_counter pattern).

        Perfect for preserving event ordering within a workflow without requiring activities.

        Returns:
            datetime: Deterministic timestamp that increments on each call

        Example:
            ```python
            def workflow(ctx):
                t1 = ctx.now_with_sequence()  # 2024-01-01 12:00:00.000000
                result = yield ctx.call_activity(some_activity, input="data")
                t2 = ctx.now_with_sequence()  # 2024-01-01 12:00:00.000001
                # t1 < t2, preserving order for telemetry
            ```
        """
        offset = timedelta(microseconds=self._timestamp_counter)
        self._timestamp_counter += 1
        return self.current_utc_datetime + offset  # type: ignore[attr-defined]

    def current_utc_datetime_with_sequence(self):
        """Alias for now_with_sequence for API parity with other SDKs."""
        return self.now_with_sequence()
