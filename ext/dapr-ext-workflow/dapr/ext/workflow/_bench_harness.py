# -*- coding: utf-8 -*-
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

"""Shared dispatch harness for the workflow benchmarks and perf regression tests.

Metrics, the mock sidecar stub, and the runners that drive ``_execute_activity`` and
``_execute_activity_async`` through ``_AsyncWorkerManager``. Imported by both
``benchmarks/bench_async_activities.py`` and ``tests/durabletask`` so they share one
dispatch harness. Internal: not part of the public API.
"""

from __future__ import annotations

import asyncio
import logging
import math
import os
import statistics
import sys
import time
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from typing import Awaitable, Callable

import dapr.ext.workflow._durabletask.internal.protos as pb
from dapr.ext.workflow._durabletask import task
from dapr.ext.workflow._durabletask.internal import shared
from dapr.ext.workflow._durabletask.worker import (
    ConcurrencyOptions,
    TaskHubGrpcWorker,
    _AsyncWorkerManager,
)

LOGGER = logging.getLogger('bench')
IS_DARWIN = sys.platform == 'darwin'

# ============================================================================
# Data classes
# ============================================================================


@dataclass(slots=True)
class LatencyStats:
    """Summary statistics for a population of end-to-end latency samples."""

    count: int
    mean_ms: float
    p50_ms: float
    p95_ms: float
    p99_ms: float
    max_ms: float

    @classmethod
    def from_samples(cls, samples_s: list[float]) -> 'LatencyStats':
        if not samples_s:
            return cls(count=0, mean_ms=0.0, p50_ms=0.0, p95_ms=0.0, p99_ms=0.0, max_ms=0.0)
        samples_ms = sorted(s * 1000.0 for s in samples_s)
        return cls(
            count=len(samples_ms),
            mean_ms=statistics.fmean(samples_ms),
            p50_ms=_percentile(samples_ms, 0.50),
            p95_ms=_percentile(samples_ms, 0.95),
            p99_ms=_percentile(samples_ms, 0.99),
            max_ms=samples_ms[-1],
        )


@dataclass(slots=True)
class ScenarioMetrics:
    """Per-scenario summary written to the results table."""

    name: str
    n_items: int
    semaphore_cap: int
    thread_pool_workers: int
    server_latency_s: float
    wallclock_s: float
    throughput_per_s: float
    latency: LatencyStats
    peak_tasks: int
    peak_queue_depth: int
    peak_rss_delta_mb: float
    notes: str = ''


@dataclass
class _Sampler:
    """Background sampler for in-flight task count, queue depth, and RSS."""

    interval_s: float = 0.05
    peak_tasks: int = 0
    peak_rss_kb: int = 0
    peak_queue_depth: int = 0
    _queues: list[asyncio.Queue] = field(default_factory=list)
    _stop_event: asyncio.Event = field(default_factory=asyncio.Event)

    def watch_queue(self, q: asyncio.Queue | None) -> None:
        if q is not None:
            self._queues.append(q)

    async def run(self) -> None:
        while not self._stop_event.is_set():
            self.peak_tasks = max(self.peak_tasks, len(asyncio.all_tasks()))
            self.peak_rss_kb = max(self.peak_rss_kb, _current_rss_kb())
            for q in self._queues:
                self.peak_queue_depth = max(self.peak_queue_depth, q.qsize())
            try:
                await asyncio.wait_for(self._stop_event.wait(), timeout=self.interval_s)
            except asyncio.TimeoutError:
                continue

    def stop(self) -> None:
        self._stop_event.set()


# ============================================================================
# Helpers
# ============================================================================


def _percentile(sorted_samples_ms: list[float], q: float) -> float:
    if not sorted_samples_ms:
        return 0.0
    if len(sorted_samples_ms) == 1:
        return sorted_samples_ms[0]
    pos = q * (len(sorted_samples_ms) - 1)
    lo = math.floor(pos)
    hi = math.ceil(pos)
    if lo == hi:
        return sorted_samples_ms[lo]
    frac = pos - lo
    return sorted_samples_ms[lo] + frac * (sorted_samples_ms[hi] - sorted_samples_ms[lo])


try:
    import resource as _resource  # POSIX only
except ImportError:
    _resource = None


def _current_rss_kb() -> int:
    """Process RSS in KB. macOS returns bytes from getrusage; Linux returns KB.
    Returns 0 on Windows since `resource` is unavailable there.
    """
    if _resource is None:
        return 0
    rss = _resource.getrusage(_resource.RUSAGE_SELF).ru_maxrss
    if IS_DARWIN:
        return rss // 1024
    return rss


# ============================================================================
# Mock sidecar stub (production response path goes through here)
# ============================================================================


class _MockSidecarStub:
    """In-process stand-in for ``TaskHubSidecarServiceStub``.

    ``_execute_activity_async`` and ``_execute_activity`` deliver responses via
    ``stub.CompleteActivityTask``. The mock records completion timestamps so the
    harness can compute end-to-end latency (submit -> delivery). ``send_latency_s``
    simulates a slow sidecar.
    """

    def __init__(self, send_latency_s: float = 0.0):
        self.send_latency_s = send_latency_s
        self.completions: dict[int, float] = {}
        self.calls = 0

    def Hello(self, *_args, **_kwargs) -> None:  # noqa: N802
        return None

    def CompleteActivityTask(self, response: pb.ActivityResponse) -> None:  # noqa: N802
        if self.send_latency_s > 0:
            time.sleep(self.send_latency_s)
        self.completions[response.taskId] = time.perf_counter()
        self.calls += 1

    def CompleteOrchestratorTask(self, *_args, **_kwargs) -> None:  # noqa: N802
        return None


def _random_payload(n: int) -> str:
    """A JSON-safe random string of ~n characters (hex of random bytes)."""
    return os.urandom(max(1, n // 2)).hex()[:n]


def _build_activity_request(
    name: str, task_id: int, instance_id: str, encoded_input: str = ''
) -> pb.ActivityRequest:
    req = pb.ActivityRequest(
        name=name,
        taskId=task_id,
        workflowInstance=pb.WorkflowInstance(instanceId=instance_id),
        parentTraceContext=pb.TraceContext(traceParent=''),
        taskExecutionId='',
    )
    if encoded_input:
        req.input.value = encoded_input
    return req


# ============================================================================
# Activity factories. Record per-invocation timestamps so the harness can
# decompose end-to-end latency into queue-wait / work / delivery.
# ============================================================================


def _async_sleep_factory(
    latency_s: float, start_ts: dict[int, float], end_ts: dict[int, float]
) -> Callable[[task.ActivityContext, object], Awaitable[None]]:
    """Build an async activity that sleeps. Records per-task start/end timestamps."""

    async def sleep(ctx: task.ActivityContext, _inp: object) -> None:
        start_ts[ctx.task_id] = time.perf_counter()
        await asyncio.sleep(latency_s)
        end_ts[ctx.task_id] = time.perf_counter()

    return sleep


def _sync_sleep_factory(
    latency_s: float, start_ts: dict[int, float], end_ts: dict[int, float]
) -> Callable[[task.ActivityContext, object], None]:
    """Build a sync activity that sleeps. Records per-task start/end timestamps."""

    def sleep(ctx: task.ActivityContext, _inp: object) -> None:
        start_ts[ctx.task_id] = time.perf_counter()
        time.sleep(latency_s)
        end_ts[ctx.task_id] = time.perf_counter()

    return sleep


def _async_payload_factory(
    latency_s: float, out_bytes: int, start_ts: dict[int, float], end_ts: dict[int, float]
) -> Callable[[task.ActivityContext, object], Awaitable[str]]:
    """Async activity that returns an ``out_bytes`` payload, exercising result serialization."""
    payload = _random_payload(out_bytes)

    async def run(ctx: task.ActivityContext, _inp: object) -> str:
        start_ts[ctx.task_id] = time.perf_counter()
        await asyncio.sleep(latency_s)
        end_ts[ctx.task_id] = time.perf_counter()
        return payload

    return run


def _sync_payload_factory(
    latency_s: float, out_bytes: int, start_ts: dict[int, float], end_ts: dict[int, float]
) -> Callable[[task.ActivityContext, object], str]:
    """Sync counterpart of ``_async_payload_factory``."""
    payload = _random_payload(out_bytes)

    def run(ctx: task.ActivityContext, _inp: object) -> str:
        start_ts[ctx.task_id] = time.perf_counter()
        time.sleep(latency_s)
        end_ts[ctx.task_id] = time.perf_counter()
        return payload

    return run


# ============================================================================
# Full-path harness. Exercises _execute_activity_async / _execute_activity
# through _AsyncWorkerManager with a mock CompleteActivityTask stub.
# ============================================================================


def _build_worker(options: ConcurrencyOptions) -> TaskHubGrpcWorker:
    """Build a TaskHubGrpcWorker without calling start(). We only need its dispatch
    code and registry; the gRPC stream is replaced by the mock stub.
    """
    return TaskHubGrpcWorker(
        host_address='in-process-mock',
        concurrency_options=options,
    )


ActivityFactory = Callable[[dict[int, float], dict[int, float]], Callable[..., object]]


def _options(semaphore_cap: int, thread_pool_workers: int) -> ConcurrencyOptions:
    return ConcurrencyOptions(
        maximum_concurrent_activity_work_items=semaphore_cap,
        maximum_concurrent_orchestration_work_items=semaphore_cap,
        maximum_thread_pool_workers=thread_pool_workers,
    )


def _activity_and_handler(
    worker: TaskHubGrpcWorker,
    kind: str,
    factory: ActivityFactory | None,
    latency_s: float,
    start_ts: dict[int, float],
    end_ts: dict[int, float],
) -> tuple[Callable[..., object], Callable[..., object]]:
    """Build the activity callable and pick the matching dispatch handler for ``kind``."""
    if kind == 'async':
        fn = (
            factory(start_ts, end_ts)
            if factory
            else _async_sleep_factory(latency_s, start_ts, end_ts)
        )
        return fn, worker._execute_activity_async
    if kind == 'sync':
        fn = (
            factory(start_ts, end_ts)
            if factory
            else _sync_sleep_factory(latency_s, start_ts, end_ts)
        )
        return fn, worker._execute_activity
    raise ValueError(f'unknown activity_kind: {kind}')


@asynccontextmanager
async def _running_manager(manager):
    """Start the manager and an RSS/task sampler; on exit drain the queue and tear down.

    Yields ``(sampler, baseline_rss_kb)``.
    """
    baseline_rss_kb = _current_rss_kb()
    sampler = _Sampler()
    sampler_task = asyncio.create_task(sampler.run())
    worker_task = asyncio.create_task(manager.run())
    while manager.activity_queue is None:
        await asyncio.sleep(0)
    sampler.watch_queue(manager.activity_queue)
    try:
        yield sampler, baseline_rss_kb
    finally:
        manager._shutdown = True
        sampler.stop()
        await asyncio.gather(worker_task, sampler_task, return_exceptions=True)
        manager.shutdown()


def _metrics(
    *,
    name: str,
    n_items: int,
    semaphore_cap: int,
    thread_pool_workers: int,
    server_latency_s: float,
    wallclock_s: float,
    e2e_samples: list[float],
    sampler: _Sampler,
    baseline_rss_kb: int,
) -> ScenarioMetrics:
    completed = len(e2e_samples) if e2e_samples else n_items
    return ScenarioMetrics(
        name=name,
        n_items=n_items,
        semaphore_cap=semaphore_cap,
        thread_pool_workers=thread_pool_workers,
        server_latency_s=server_latency_s,
        wallclock_s=wallclock_s,
        throughput_per_s=completed / wallclock_s if wallclock_s > 0 else 0.0,
        latency=LatencyStats.from_samples(e2e_samples),
        peak_tasks=sampler.peak_tasks,
        peak_queue_depth=sampler.peak_queue_depth,
        peak_rss_delta_mb=max(0.0, (sampler.peak_rss_kb - baseline_rss_kb) / 1024.0),
    )


def _make_activity_context(orchestration_id: str, task_id: int) -> task.ActivityContext:
    return task.ActivityContext(orchestration_id, task_id, '', propagated_history=None)


@dataclass(slots=True)
class SustainedMetrics:
    """Steady-state metrics for the sustained-load scenario."""

    target_rate_per_s: float
    duration_s: float
    submitted: int
    completed: int
    wallclock_s: float
    throughput_per_s: float
    latency_overall: LatencyStats
    latency_first_quarter: LatencyStats
    latency_last_quarter: LatencyStats
    peak_tasks: int
    peak_queue_depth: int
    peak_rss_delta_mb: float


async def _run_full(
    *,
    name: str,
    n_items: int,
    semaphore_cap: int,
    thread_pool_workers: int,
    server_latency_s: float,
    activity_kind: str,
    activity_factory: ActivityFactory | None = None,
    input_bytes: int = 0,
) -> ScenarioMetrics:
    """Submit ``n_items`` activities through the production dispatch path, timing the batch.

    ``input_bytes`` attaches a serialized input payload to each request so the executor's
    input deserialization is part of the measurement.
    """
    worker = _build_worker(_options(semaphore_cap, thread_pool_workers))
    manager = worker._async_worker_manager
    stub = _MockSidecarStub()
    start_ts: dict[int, float] = {}
    end_ts: dict[int, float] = {}
    activity_fn, handler = _activity_and_handler(
        worker, activity_kind, activity_factory, server_latency_s, start_ts, end_ts
    )
    activity_name = f'bench_{activity_kind}'
    worker._registry.add_named_activity(activity_name, activity_fn)
    encoded_input = shared.to_json(_random_payload(input_bytes)) if input_bytes else ''

    submit_ts: dict[int, float] = {}
    async with _running_manager(manager) as (sampler, baseline_rss_kb):
        submit_start = time.perf_counter()
        for i in range(n_items):
            req = _build_activity_request(activity_name, i, 'bench', encoded_input)
            submit_ts[i] = time.perf_counter()
            manager.submit_activity(handler, activity_fn, req, stub, '')
        await manager.activity_queue.join()
        wallclock_s = time.perf_counter() - submit_start

    e2e = [stub.completions[i] - t for i, t in submit_ts.items() if i in stub.completions]
    return _metrics(
        name=name,
        n_items=n_items,
        semaphore_cap=semaphore_cap,
        thread_pool_workers=thread_pool_workers,
        server_latency_s=server_latency_s,
        wallclock_s=wallclock_s,
        e2e_samples=e2e,
        sampler=sampler,
        baseline_rss_kb=baseline_rss_kb,
    )


async def _run_lite(
    *,
    name: str,
    activity: Callable,
    n_items: int,
    semaphore_cap: int,
    thread_pool_workers: int,
    server_latency_s: float,
) -> ScenarioMetrics:
    """Submit activities straight to a bare manager (no proto/stub), for the OOM check."""
    manager = _AsyncWorkerManager(_options(semaphore_cap, thread_pool_workers), logger=LOGGER)
    async with _running_manager(manager) as (sampler, baseline_rss_kb):
        start = time.perf_counter()
        for i in range(n_items):
            manager.submit_activity(activity, _make_activity_context('bench', i), None)
        await manager.activity_queue.join()
        wallclock_s = time.perf_counter() - start

    return _metrics(
        name=name,
        n_items=n_items,
        semaphore_cap=semaphore_cap,
        thread_pool_workers=thread_pool_workers,
        server_latency_s=server_latency_s,
        wallclock_s=wallclock_s,
        e2e_samples=[],
        sampler=sampler,
        baseline_rss_kb=baseline_rss_kb,
    )


async def _run_sustained(
    *,
    duration_s: float,
    target_rate_per_s: float,
    semaphore_cap: int,
    thread_pool_workers: int,
    server_latency_s: float,
    activity_kind: str = 'async',
) -> SustainedMetrics:
    """Submit open-loop at ``target_rate_per_s`` for ``duration_s``, then drain."""
    worker = _build_worker(_options(semaphore_cap, thread_pool_workers))
    manager = worker._async_worker_manager
    stub = _MockSidecarStub()
    start_ts: dict[int, float] = {}
    end_ts: dict[int, float] = {}
    activity_fn, handler = _activity_and_handler(
        worker, activity_kind, None, server_latency_s, start_ts, end_ts
    )
    activity_name = f'bench_sustained_{activity_kind}'
    worker._registry.add_named_activity(activity_name, activity_fn)

    submit_ts: dict[int, float] = {}
    submit_interval = 1.0 / target_rate_per_s
    submitted = 0
    async with _running_manager(manager) as (sampler, baseline_rss_kb):
        bench_start = time.perf_counter()
        next_submit = bench_start
        while time.perf_counter() - bench_start < duration_s:
            if time.perf_counter() >= next_submit:
                req = _build_activity_request(activity_name, submitted, 'bench-sus')
                submit_ts[submitted] = time.perf_counter()
                manager.submit_activity(handler, activity_fn, req, stub, '')
                submitted += 1
                next_submit += submit_interval
                continue
            await asyncio.sleep(max(0.0, next_submit - time.perf_counter()))
        await manager.activity_queue.join()
        wallclock_s = time.perf_counter() - bench_start

    samples = sorted(
        (t, stub.completions[i] - t) for i, t in submit_ts.items() if i in stub.completions
    )
    overall = [d for _, d in samples]
    quarter = max(1, len(overall) // 4)
    return SustainedMetrics(
        target_rate_per_s=target_rate_per_s,
        duration_s=duration_s,
        submitted=submitted,
        completed=len(overall),
        wallclock_s=wallclock_s,
        throughput_per_s=len(overall) / wallclock_s if wallclock_s > 0 else 0.0,
        latency_overall=LatencyStats.from_samples(overall),
        latency_first_quarter=LatencyStats.from_samples(overall[:quarter]),
        latency_last_quarter=LatencyStats.from_samples(overall[-quarter:]),
        peak_tasks=sampler.peak_tasks,
        peak_queue_depth=sampler.peak_queue_depth,
        peak_rss_delta_mb=max(0.0, (sampler.peak_rss_kb - baseline_rss_kb) / 1024.0),
    )
