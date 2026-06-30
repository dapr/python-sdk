# Copyright 2026 The Dapr Authors
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#     http://www.apache.org/licenses/LICENSE-2.0
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Unit tests for the worker's stateful-history cache and history reconstruction.

These mirror the Go reference (durabletask-go client/worker_history_test.go): the cache
bounds (TTL, instance count, byte budget) with LRU eviction, and the worker's resolution
of full vs delta work items with a GetInstanceHistory fallback on a cache miss.
"""

from typing import cast

import dapr.ext.workflow._durabletask.internal.orchestrator_service_pb2_grpc as stubs
import dapr.ext.workflow._durabletask.internal.protos as pb
from dapr.ext.workflow._durabletask.worker import TaskHubGrpcWorker, _WorkflowHistoryCache


class _Clock:
    """A controllable monotonic clock for deterministic TTL tests."""

    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        return self.now


def _events(count: int) -> list[pb.HistoryEvent]:
    """Events with non-zero serialized size (eventId 0 is the proto default → 0 bytes)."""
    return [pb.HistoryEvent(eventId=i + 1) for i in range(count)]


class _FakeStub:
    """A stub whose GetInstanceHistory returns a fixed history and counts calls."""

    def __init__(self, events: list[pb.HistoryEvent]) -> None:
        self._events = events
        self.get_instance_history_calls = 0

    def GetInstanceHistory(self, request: pb.GetInstanceHistoryRequest):
        self.get_instance_history_calls += 1
        return pb.GetInstanceHistoryResponse(events=self._events)


# --- cache bounds -----------------------------------------------------------------


def test_get_put_delete_reset():
    cache = _WorkflowHistoryCache()

    assert cache.get('a') is None
    cache.put('a', _events(3))
    cached = cache.get('a')
    assert cached is not None and len(cached) == 3

    cache.delete('a')
    assert cache.get('a') is None

    cache.put('b', _events(1))
    cache.reset()
    assert cache.get('b') is None


def test_count_cap_evicts_lru():
    clock = _Clock()
    cache = _WorkflowHistoryCache(max_instances=2, clock=clock)

    cache.put('a', _events(1))
    clock.now += 1
    cache.put('b', _events(1))
    clock.now += 1
    cache.put('c', _events(1))  # over the cap → evict LRU ('a')

    assert cache.get('a') is None
    assert cache.get('b') is not None
    assert cache.get('c') is not None


def test_byte_cap_evicts_lru():
    entry_bytes = sum(e.ByteSize() for e in _events(4))
    assert entry_bytes > 0
    clock = _Clock()
    cache = _WorkflowHistoryCache(max_bytes=entry_bytes + 1, clock=clock)

    cache.put('a', _events(4))
    clock.now += 1
    cache.put('b', _events(4))  # two entries exceed the byte budget → evict LRU ('a')

    assert cache.get('a') is None
    assert cache.get('b') is not None
    assert cache._total_bytes <= entry_bytes + 1


def test_single_oversized_entry_kept():
    cache = _WorkflowHistoryCache(max_bytes=1)
    cache.put('big', _events(5))
    assert cache.get('big') is not None


def test_byte_accounting():
    cache = _WorkflowHistoryCache()

    cache.put('a', _events(3))
    cache.put('b', _events(2))
    assert cache._total_bytes == sum(e.ByteSize() for e in _events(3)) + sum(
        e.ByteSize() for e in _events(2)
    )

    cache.put('a', _events(6))  # replace adjusts the running total to the new size
    assert cache._total_bytes == sum(e.ByteSize() for e in _events(6)) + sum(
        e.ByteSize() for e in _events(2)
    )

    cache.delete('a')
    assert cache._total_bytes == sum(e.ByteSize() for e in _events(2))

    cache.reset()
    assert cache._total_bytes == 0


def test_ttl_sweep_is_sliding():
    clock = _Clock()
    cache = _WorkflowHistoryCache(ttl=60.0, clock=clock)

    cache.put('idle', _events(2))
    cache.put('active', _events(2))

    clock.now += 120  # past the TTL...
    assert cache.get('active') is not None  # ...but a turn refreshes 'active'

    cache.sweep_expired()
    assert cache.get('idle') is None
    assert cache.get('active') is not None


def test_non_positive_config_uses_defaults():
    cache = _WorkflowHistoryCache(ttl=0, max_instances=-1, max_bytes=-5)
    assert cache._ttl > 0
    assert cache._max_instances > 0
    assert cache._max_bytes == 0  # unlimited


# --- worker history resolution ----------------------------------------------------


def _worker(**kwargs) -> TaskHubGrpcWorker:
    return TaskHubGrpcWorker(host_address='localhost:0', **kwargs)


def _resolve(
    worker: TaskHubGrpcWorker, req: pb.WorkflowRequest, stub: _FakeStub
) -> list[pb.HistoryEvent]:
    return worker._resolve_history(req, cast(stubs.TaskHubSidecarServiceStub, stub))


def test_resolve_full_send_returns_past_events():
    worker = _worker()
    stub = _FakeStub(_events(99))
    req = pb.WorkflowRequest(instanceId='a', pastEvents=_events(4))

    resolved = _resolve(worker, req, stub)
    assert len(resolved) == 4
    assert stub.get_instance_history_calls == 0


def test_resolve_cache_hit_reconstructs():
    worker = _worker()
    worker._history_cache.put('a', _events(5))
    stub = _FakeStub(_events(99))
    req = pb.WorkflowRequest(instanceId='a', pastEvents=_events(3))
    req.cachedHistory.eventCount = 5

    resolved = _resolve(worker, req, stub)
    assert len(resolved) == 8  # cached prefix (5) + delta (3)
    assert stub.get_instance_history_calls == 0


def test_resolve_cache_miss_fetches_full_history():
    worker = _worker()
    stub = _FakeStub(_events(7))
    req = pb.WorkflowRequest(instanceId='a', pastEvents=_events(3))
    req.cachedHistory.eventCount = 5

    resolved = _resolve(worker, req, stub)
    assert len(resolved) == 7  # recovered via GetInstanceHistory
    assert stub.get_instance_history_calls == 1


def test_resolve_length_mismatch_is_miss():
    worker = _worker()
    worker._history_cache.put('a', _events(4))  # worker holds 4...
    stub = _FakeStub(_events(7))
    req = pb.WorkflowRequest(instanceId='a', pastEvents=_events(3))
    req.cachedHistory.eventCount = 5  # ...but the sidecar expects 5 → fetch

    resolved = _resolve(worker, req, stub)
    assert len(resolved) == 7
    assert stub.get_instance_history_calls == 1


def test_update_cache_stores_then_evicts_on_complete():
    worker = _worker()
    running = [pb.WorkflowAction(scheduleTask=pb.ScheduleTaskAction())]
    worker._update_history_cache('a', _events(6), running)
    assert worker._history_cache.get('a') is not None

    completed = [pb.WorkflowAction(completeWorkflow=pb.CompleteWorkflowAction())]
    worker._update_history_cache('a', _events(6), completed)
    assert worker._history_cache.get('a') is None


def test_disabled_worker_does_not_cache_and_passes_full_history():
    worker = _worker(disable_stateful_history=True)
    worker._update_history_cache('a', _events(6), [])
    assert worker._history_cache.get('a') is None

    stub = _FakeStub(_events(99))
    req = pb.WorkflowRequest(instanceId='a', pastEvents=_events(4))
    resolved = _resolve(worker, req, stub)
    assert len(resolved) == 4
    assert stub.get_instance_history_calls == 0
