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

import random
import uuid
from datetime import datetime, timezone

import pytest

from durabletask.deterministic import (
    DeterminismSeed,
    derive_seed,
    deterministic_random,
    deterministic_uuid4,
    deterministic_uuid_v5,
)
from durabletask.worker import _RuntimeOrchestrationContext


class TestDeterminismSeed:
    """Test DeterminismSeed dataclass and its methods."""

    def test_to_int_produces_consistent_result(self):
        """Test that to_int produces the same result for same inputs."""
        seed1 = DeterminismSeed(instance_id="test-123", orchestration_unix_ts=1234567890)
        seed2 = DeterminismSeed(instance_id="test-123", orchestration_unix_ts=1234567890)
        assert seed1.to_int() == seed2.to_int()

    def test_to_int_produces_different_results_for_different_instance_ids(self):
        """Test that different instance IDs produce different seeds."""
        seed1 = DeterminismSeed(instance_id="test-123", orchestration_unix_ts=1234567890)
        seed2 = DeterminismSeed(instance_id="test-456", orchestration_unix_ts=1234567890)
        assert seed1.to_int() != seed2.to_int()

    def test_to_int_produces_different_results_for_different_timestamps(self):
        """Test that different timestamps produce different seeds."""
        seed1 = DeterminismSeed(instance_id="test-123", orchestration_unix_ts=1234567890)
        seed2 = DeterminismSeed(instance_id="test-123", orchestration_unix_ts=1234567891)
        assert seed1.to_int() != seed2.to_int()

    def test_to_int_returns_positive_integer(self):
        """Test that to_int returns a positive integer."""
        seed = DeterminismSeed(instance_id="test-123", orchestration_unix_ts=1234567890)
        result = seed.to_int()
        assert isinstance(result, int)
        assert result >= 0


class TestDeriveSeed:
    """Test derive_seed function."""

    def test_derive_seed_is_deterministic(self):
        """Test that derive_seed produces consistent results."""
        instance_id = "test-instance"
        dt = datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        seed1 = derive_seed(instance_id, dt)
        seed2 = derive_seed(instance_id, dt)
        assert seed1 == seed2

    def test_derive_seed_different_for_different_times(self):
        """Test that different times produce different seeds."""
        instance_id = "test-instance"
        dt1 = datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        dt2 = datetime(2025, 1, 1, 12, 0, 1, tzinfo=timezone.utc)
        seed1 = derive_seed(instance_id, dt1)
        seed2 = derive_seed(instance_id, dt2)
        assert seed1 != seed2

    def test_derive_seed_handles_timezone_aware_datetime(self):
        """Test that derive_seed works with timezone-aware datetimes."""
        instance_id = "test-instance"
        dt = datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        seed = derive_seed(instance_id, dt)
        assert isinstance(seed, int)


class TestDeterministicRandom:
    """Test deterministic_random function."""

    def test_deterministic_random_returns_random_object(self):
        """Test that deterministic_random returns a Random instance."""
        instance_id = "test-instance"
        dt = datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        rnd = deterministic_random(instance_id, dt)
        assert isinstance(rnd, random.Random)

    def test_deterministic_random_produces_same_sequence(self):
        """Test that same inputs produce same random sequence."""
        instance_id = "test-instance"
        dt = datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        rnd1 = deterministic_random(instance_id, dt)
        rnd2 = deterministic_random(instance_id, dt)

        sequence1 = [rnd1.random() for _ in range(10)]
        sequence2 = [rnd2.random() for _ in range(10)]
        assert sequence1 == sequence2

    def test_deterministic_random_different_for_different_inputs(self):
        """Test that different inputs produce different sequences."""
        dt = datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        rnd1 = deterministic_random("instance-1", dt)
        rnd2 = deterministic_random("instance-2", dt)

        val1 = rnd1.random()
        val2 = rnd2.random()
        assert val1 != val2


class TestDeterministicUuid4:
    """Test deterministic_uuid4 function."""

    def test_deterministic_uuid4_returns_valid_uuid(self):
        """Test that deterministic_uuid4 returns a valid UUID4."""
        rnd = random.Random(42)
        result = deterministic_uuid4(rnd)
        assert isinstance(result, uuid.UUID)
        assert result.version == 4

    def test_deterministic_uuid4_is_deterministic(self):
        """Test that same random state produces same UUID."""
        rnd1 = random.Random(42)
        rnd2 = random.Random(42)
        uuid1 = deterministic_uuid4(rnd1)
        uuid2 = deterministic_uuid4(rnd2)
        assert uuid1 == uuid2

    def test_deterministic_uuid4_different_for_different_seeds(self):
        """Test that different seeds produce different UUIDs."""
        rnd1 = random.Random(42)
        rnd2 = random.Random(43)
        uuid1 = deterministic_uuid4(rnd1)
        uuid2 = deterministic_uuid4(rnd2)
        assert uuid1 != uuid2


class TestDeterministicUuidV5:
    """Test deterministic_uuid_v5 function (matching .NET implementation)."""

    def test_deterministic_uuid_v5_returns_valid_uuid(self):
        """Test that deterministic_uuid_v5 returns a valid UUID v5."""
        dt = datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        result = deterministic_uuid_v5("test-instance", dt, 0)
        assert isinstance(result, uuid.UUID)
        assert result.version == 5

    def test_deterministic_uuid_v5_is_deterministic(self):
        """Test that same inputs produce same UUID."""
        dt = datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        uuid1 = deterministic_uuid_v5("test-instance", dt, 0)
        uuid2 = deterministic_uuid_v5("test-instance", dt, 0)
        assert uuid1 == uuid2

    def test_deterministic_uuid_v5_different_for_different_counters(self):
        """Test that different counters produce different UUIDs."""
        dt = datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        uuid1 = deterministic_uuid_v5("test-instance", dt, 0)
        uuid2 = deterministic_uuid_v5("test-instance", dt, 1)
        assert uuid1 != uuid2

    def test_deterministic_uuid_v5_different_for_different_instance_ids(self):
        """Test that different instance IDs produce different UUIDs."""
        dt = datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        uuid1 = deterministic_uuid_v5("instance-1", dt, 0)
        uuid2 = deterministic_uuid_v5("instance-2", dt, 0)
        assert uuid1 != uuid2

    def test_deterministic_uuid_v5_different_for_different_datetimes(self):
        """Test that different datetimes produce different UUIDs."""
        dt1 = datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        dt2 = datetime(2025, 1, 1, 12, 0, 1, tzinfo=timezone.utc)
        uuid1 = deterministic_uuid_v5("test-instance", dt1, 0)
        uuid2 = deterministic_uuid_v5("test-instance", dt2, 0)
        assert uuid1 != uuid2

    def test_deterministic_uuid_v5_matches_expected_format(self):
        """Test that UUID v5 uses the correct namespace."""
        dt = datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        result = deterministic_uuid_v5("test-instance", dt, 0)
        # Should be deterministic - same inputs always produce same output
        expected = deterministic_uuid_v5("test-instance", dt, 0)
        assert result == expected

    def test_deterministic_uuid_v5_counter_sequence(self):
        """Test that incrementing counter produces different UUIDs in sequence."""
        dt = datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        uuids = [deterministic_uuid_v5("test-instance", dt, i) for i in range(5)]
        # All should be different
        assert len(set(uuids)) == 5
        # But calling with same counter should produce same UUID
        assert uuids[0] == deterministic_uuid_v5("test-instance", dt, 0)
        assert uuids[4] == deterministic_uuid_v5("test-instance", dt, 4)


def mock_deterministic_context(
    instance_id: str, current_utc_datetime: datetime
) -> _RuntimeOrchestrationContext:
    """Mock context for testing DeterministicContextMixin."""
    ctx = _RuntimeOrchestrationContext(instance_id)
    ctx.current_utc_datetime = current_utc_datetime
    return ctx


class TestDeterministicContextMixin:
    """Test DeterministicContextMixin methods."""

    def test_now_returns_current_utc_datetime(self):
        """Test that now() returns the orchestration time."""
        dt = datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        ctx = mock_deterministic_context("test-instance", dt)
        assert ctx.now() == dt

    def test_random_returns_deterministic_prng(self):
        """Test that random() returns a deterministic PRNG."""
        dt = datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        ctx = mock_deterministic_context("test-instance", dt)
        rnd1 = ctx.random()
        rnd2 = ctx.random()

        # Both should produce same sequence
        assert isinstance(rnd1, random.Random)
        assert isinstance(rnd2, random.Random)
        assert rnd1.random() == rnd2.random()

    def test_random_has_deterministic_marker(self):
        """Test that random() sets _dt_deterministic marker."""
        dt = datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        ctx = mock_deterministic_context("test-instance", dt)
        rnd = ctx.random()
        assert hasattr(rnd, "_dt_deterministic")
        assert rnd._dt_deterministic is True

    def test_uuid4_generates_deterministic_uuid(self):
        """Test that uuid4() generates deterministic UUIDs v5 with counter."""
        dt = datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        ctx1 = mock_deterministic_context("test-instance", dt)
        ctx2 = mock_deterministic_context("test-instance", dt)

        uuid1 = ctx1.uuid4()
        uuid2 = ctx2.uuid4()

        assert isinstance(uuid1, uuid.UUID)
        assert uuid1.version == 5  # Now using UUID v5 like .NET
        assert uuid1 == uuid2  # Same counter (0) produces same UUID

    def test_uuid4_increments_counter(self):
        """Test that uuid4() increments counter producing different UUIDs."""
        dt = datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        ctx = mock_deterministic_context("test-instance", dt)

        uuid1 = ctx.uuid4()  # counter=0
        uuid2 = ctx.uuid4()  # counter=1
        uuid3 = ctx.uuid4()  # counter=2

        # All should be different due to counter
        assert uuid1 != uuid2
        assert uuid2 != uuid3
        assert uuid1 != uuid3

    def test_uuid4_counter_resets_on_replay(self):
        """Test that counter resets on new context (simulating replay)."""
        dt = datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc)

        # First execution
        ctx1 = mock_deterministic_context("test-instance", dt)
        uuid1_first = ctx1.uuid4()  # counter=0
        uuid1_second = ctx1.uuid4()  # counter=1

        # Replay - new context, counter resets
        ctx2 = mock_deterministic_context("test-instance", dt)
        uuid2_first = ctx2.uuid4()  # counter=0
        uuid2_second = ctx2.uuid4()  # counter=1

        # Same counter values produce same UUIDs (determinism!)
        assert uuid1_first == uuid2_first
        assert uuid1_second == uuid2_second

    def test_new_guid_is_alias_for_uuid4(self):
        """Test that new_guid() is an alias for uuid4()."""
        dt = datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        ctx = mock_deterministic_context("test-instance", dt)

        guid1 = ctx.new_guid()  # counter=0
        guid2 = ctx.uuid4()  # counter=1

        # Both should be v5 UUIDs, but different due to counter increment
        assert isinstance(guid1, uuid.UUID)
        assert isinstance(guid2, uuid.UUID)
        assert guid1.version == 5
        assert guid2.version == 5
        assert guid1 != guid2  # Different due to counter

        # Verify determinism - same counter produces same UUID
        ctx2 = mock_deterministic_context("test-instance", dt)
        guid3 = ctx2.new_guid()  # counter=0
        assert guid3 == guid1  # Same as first call

    def test_random_string_generates_string_of_correct_length(self):
        """Test that random_string() generates string of specified length."""
        dt = datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        ctx = mock_deterministic_context("test-instance", dt)

        s = ctx.random_string(10)
        assert len(s) == 10

    def test_random_string_is_deterministic(self):
        """Test that random_string() produces consistent results."""
        dt = datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        ctx1 = mock_deterministic_context("test-instance", dt)
        ctx2 = mock_deterministic_context("test-instance", dt)

        s1 = ctx1.random_string(20)
        s2 = ctx2.random_string(20)
        assert s1 == s2

    def test_random_string_uses_default_alphabet(self):
        """Test that random_string() uses alphanumeric characters by default."""
        dt = datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        ctx = mock_deterministic_context("test-instance", dt)

        s = ctx.random_string(100)
        assert all(c.isalnum() for c in s)

    def test_random_string_uses_custom_alphabet(self):
        """Test that random_string() respects custom alphabet."""
        dt = datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        ctx = mock_deterministic_context("test-instance", dt)

        s = ctx.random_string(50, alphabet="ABC")
        assert all(c in "ABC" for c in s)

    def test_random_string_raises_on_negative_length(self):
        """Test that random_string() raises ValueError for negative length."""
        dt = datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        ctx = mock_deterministic_context("test-instance", dt)

        with pytest.raises(ValueError, match="length must be non-negative"):
            ctx.random_string(-1)

    def test_random_string_raises_on_empty_alphabet(self):
        """Test that random_string() raises ValueError for empty alphabet."""
        dt = datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        ctx = mock_deterministic_context("test-instance", dt)

        with pytest.raises(ValueError, match="alphabet must not be empty"):
            ctx.random_string(10, alphabet="")

    def test_random_string_handles_zero_length(self):
        """Test that random_string() handles zero length correctly."""
        dt = datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        ctx = mock_deterministic_context("test-instance", dt)

        s = ctx.random_string(0)
        assert s == ""

    def test_random_int_generates_int_in_range(self):
        """Test that random_int() generates integer in specified range."""
        dt = datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        ctx = mock_deterministic_context("test-instance", dt)

        for _ in range(10):
            val = ctx.random_int(10, 20)
            assert 10 <= val <= 20

    def test_random_int_is_deterministic(self):
        """Test that random_int() produces consistent results."""
        dt = datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        ctx1 = mock_deterministic_context("test-instance", dt)
        ctx2 = mock_deterministic_context("test-instance", dt)

        val1 = ctx1.random_int(0, 1000)
        val2 = ctx2.random_int(0, 1000)
        assert val1 == val2

    def test_random_int_uses_default_range(self):
        """Test that random_int() uses default range when not specified."""
        dt = datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        ctx = mock_deterministic_context("test-instance", dt)

        val = ctx.random_int()
        assert 0 <= val <= 2**31 - 1

    def test_random_int_raises_on_invalid_range(self):
        """Test that random_int() raises ValueError when min > max."""
        dt = datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        ctx = mock_deterministic_context("test-instance", dt)

        with pytest.raises(ValueError, match="min_value must be <= max_value"):
            ctx.random_int(20, 10)

    def test_random_int_handles_same_min_and_max(self):
        """Test that random_int() handles case where min equals max."""
        dt = datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        ctx = mock_deterministic_context("test-instance", dt)

        val = ctx.random_int(42, 42)
        assert val == 42

    def test_random_choice_picks_from_sequence(self):
        """Test that random_choice() picks element from sequence."""
        dt = datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        ctx = mock_deterministic_context("test-instance", dt)

        choices = ["a", "b", "c", "d", "e"]
        result = ctx.random_choice(choices)
        assert result in choices

    def test_random_choice_is_deterministic(self):
        """Test that random_choice() produces consistent results."""
        dt = datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        ctx1 = mock_deterministic_context("test-instance", dt)
        ctx2 = mock_deterministic_context("test-instance", dt)

        choices = list(range(100))
        result1 = ctx1.random_choice(choices)
        result2 = ctx2.random_choice(choices)
        assert result1 == result2

    def test_random_choice_raises_on_empty_sequence(self):
        """Test that random_choice() raises IndexError for empty sequence."""
        dt = datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        ctx = mock_deterministic_context("test-instance", dt)

        with pytest.raises(IndexError, match="Cannot choose from empty sequence"):
            ctx.random_choice([])

    def test_random_choice_works_with_different_sequence_types(self):
        """Test that random_choice() works with various sequence types."""
        dt = datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        ctx = mock_deterministic_context("test-instance", dt)

        # List
        result = ctx.random_choice([1, 2, 3])
        assert result in [1, 2, 3]

        # Reset context for deterministic behavior
        ctx = mock_deterministic_context("test-instance", dt)
        # Tuple
        result = ctx.random_choice((1, 2, 3))
        assert result in (1, 2, 3)

        # Reset context for deterministic behavior
        ctx = mock_deterministic_context("test-instance", dt)
        # String
        result = ctx.random_choice("abc")
        assert result in "abc"
