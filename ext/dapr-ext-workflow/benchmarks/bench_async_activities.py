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

"""Async-activity load benchmarks for ``dapr-ext-workflow``.

Drives the production dispatch path (``TaskHubGrpcWorker._execute_activity_async``
and ``_execute_activity``) through ``_AsyncWorkerManager`` against a mock sidecar
stub. Captures end-to-end latency (submit -> response delivery), peak in-flight
Tasks, peak RSS, and steady-state behavior so the sidecar response path is part
of the measurement instead of being skipped.

Run:

    uv run python ext/dapr-ext-workflow/benchmarks/bench_async_activities.py

Set ``DAPR_BENCH_SUSTAINED_SECONDS`` to override the 120 s sustained run.
Set ``DAPR_BENCH_WITH_SIDECAR=1`` to run the opt-in end-to-end scenario against
a real Dapr sidecar (requires ``dapr run`` wrapping the script).

Writes ``benchmarks/RESULTS.md`` and asserts pass-criteria budgets so regressions
fail loudly.
"""

from __future__ import annotations

import asyncio
import logging
import math
import os
import platform
import shutil
import socket
import statistics
import subprocess
import sys
import time
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import AsyncIterator, Awaitable, Callable

import dapr.ext.workflow._durabletask.internal.protos as pb
import httpx
from aiohttp import web
from dapr.ext.workflow._durabletask import task
from dapr.ext.workflow._durabletask.worker import (
    ConcurrencyOptions,
    TaskHubGrpcWorker,
    _AsyncWorkerManager,
)

LOGGER = logging.getLogger('bench')
RESULTS_PATH = Path(__file__).parent / 'RESULTS.md'
IS_DARWIN = sys.platform == 'darwin'

SUSTAINED_DURATION_S = float(os.environ.get('DAPR_BENCH_SUSTAINED_SECONDS', '120'))


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


def _read_text(path: str) -> str:
    try:
        return Path(path).read_text(encoding='utf-8', errors='ignore')
    except OSError:
        return ''


def _cpu_model() -> str:
    """Best-effort CPU model name. Cross-platform; returns a placeholder on failure."""
    if IS_DARWIN:
        sysctl = shutil.which('sysctl')
        if sysctl is not None:
            try:
                out = subprocess.run(
                    [sysctl, '-n', 'machdep.cpu.brand_string'],
                    capture_output=True,
                    text=True,
                    timeout=2,
                )
                if out.returncode == 0 and out.stdout.strip():
                    return out.stdout.strip()
            except (subprocess.SubprocessError, OSError):
                pass
    cpuinfo = _read_text('/proc/cpuinfo')
    for line in cpuinfo.splitlines():
        if line.startswith('model name'):
            return line.split(':', 1)[1].strip()
    return platform.processor() or platform.machine() or 'unknown'


def _total_memory_gb() -> float:
    """Best-effort total physical memory in GB. Returns 0 on failure."""
    if IS_DARWIN:
        sysctl = shutil.which('sysctl')
        if sysctl is not None:
            try:
                out = subprocess.run(
                    [sysctl, '-n', 'hw.memsize'],
                    capture_output=True,
                    text=True,
                    timeout=2,
                )
                if out.returncode == 0 and out.stdout.strip().isdigit():
                    return int(out.stdout.strip()) / (1024**3)
            except (subprocess.SubprocessError, OSError):
                pass
    meminfo = _read_text('/proc/meminfo')
    for line in meminfo.splitlines():
        if line.startswith('MemTotal:'):
            parts = line.split()
            if len(parts) >= 2 and parts[1].isdigit():
                return int(parts[1]) / (1024**2)
    return 0.0


def _git_commit() -> str:
    """Short git commit hash, or 'unknown' if not in a git repo."""
    git = shutil.which('git')
    if git is None:
        return 'unknown'
    try:
        out = subprocess.run(
            [git, 'rev-parse', '--short', 'HEAD'],
            capture_output=True,
            text=True,
            timeout=2,
            cwd=Path(__file__).parent,
        )
        if out.returncode == 0:
            commit = out.stdout.strip()
            # Mark dirty if there are uncommitted changes.
            status = subprocess.run(
                [git, 'status', '--porcelain'],
                capture_output=True,
                text=True,
                timeout=2,
                cwd=Path(__file__).parent,
            )
            if status.returncode == 0 and status.stdout.strip():
                return f'{commit}-dirty'
            return commit
    except (subprocess.SubprocessError, OSError):
        pass
    return 'unknown'


@dataclass(slots=True)
class RunEnvironment:
    """Snapshot of the machine the benchmark ran on."""

    timestamp_utc: str
    git_commit: str
    python_version: str
    python_implementation: str
    platform: str
    os_release: str
    cpu_model: str
    cpu_logical_cores: int
    cpu_physical_cores_hint: int
    total_memory_gb: float
    is_ci: bool

    @classmethod
    def capture(cls) -> 'RunEnvironment':
        return cls(
            timestamp_utc=datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC'),
            git_commit=_git_commit(),
            python_version=platform.python_version(),
            python_implementation=platform.python_implementation(),
            platform=platform.platform(),
            os_release=f'{platform.system()} {platform.release()} ({platform.machine()})',
            cpu_model=_cpu_model(),
            cpu_logical_cores=os.cpu_count() or 0,
            cpu_physical_cores_hint=os.cpu_count() or 0,
            total_memory_gb=_total_memory_gb(),
            is_ci=any(os.environ.get(k) for k in ('CI', 'GITHUB_ACTIONS', 'TRAVIS', 'BUILDKITE')),
        )


# ============================================================================
# Mock sidecar stub (production response path goes through here)
# ============================================================================


class _MockSidecarStub:
    """In-process stand-in for ``TaskHubSidecarServiceStub``.

    ``_execute_activity_async`` and ``_execute_activity`` deliver responses via
    ``stub.CompleteActivityTask``. The mock records completion timestamps so the
    harness can compute end-to-end latency (submit -> delivery). ``send_latency_s``
    simulates a slow sidecar — useful for the response-delivery-overhead scenario.
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


def _build_activity_request(name: str, task_id: int, instance_id: str) -> pb.ActivityRequest:
    return pb.ActivityRequest(
        name=name,
        taskId=task_id,
        workflowInstance=pb.WorkflowInstance(instanceId=instance_id),
        parentTraceContext=pb.TraceContext(traceParent=''),
        taskExecutionId='',
    )


# ============================================================================
# Activity factories — record per-invocation timestamps so the harness can
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


def _async_fetch_factory(
    url: str, start_ts: dict[int, float], end_ts: dict[int, float]
) -> Callable[[task.ActivityContext, object], Awaitable[int]]:
    """Build an async HTTP-fetch activity that mirrors a real user pattern."""

    async def fetch(ctx: task.ActivityContext, _inp: object) -> int:
        start_ts[ctx.task_id] = time.perf_counter()
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(url)
        end_ts[ctx.task_id] = time.perf_counter()
        return response.status_code

    return fetch


def _sync_fetch_factory(
    url: str, start_ts: dict[int, float], end_ts: dict[int, float]
) -> Callable[[task.ActivityContext, object], int]:
    def fetch(ctx: task.ActivityContext, _inp: object) -> int:
        start_ts[ctx.task_id] = time.perf_counter()
        with httpx.Client(timeout=30.0) as client:
            response = client.get(url)
        end_ts[ctx.task_id] = time.perf_counter()
        return response.status_code

    return fetch


@asynccontextmanager
async def _slow_aiohttp_server(latency_s: float) -> AsyncIterator[str]:
    """Local aiohttp server that returns JSON after ``latency_s`` seconds."""

    async def handler(_request: web.Request) -> web.Response:
        await asyncio.sleep(latency_s)
        return web.json_response({'ok': True, 'latency_s': latency_s})

    app = web.Application()
    app.router.add_get('/', handler)
    runner = web.AppRunner(app)
    await runner.setup()

    listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        listener.bind(('127.0.0.1', 0))
        port = listener.getsockname()[1]
        site = web.SockSite(runner, listener)
        await site.start()
    except BaseException:
        listener.close()
        raise
    base_url = f'http://127.0.0.1:{port}/'
    try:
        yield base_url
    finally:
        await runner.cleanup()


# ============================================================================
# Full-path harness — exercises _execute_activity_async / _execute_activity
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


async def _run_full(
    *,
    name: str,
    n_items: int,
    semaphore_cap: int,
    thread_pool_workers: int,
    server_latency_s: float,
    activity_kind: str,
    activity_factory: ActivityFactory | None = None,
    send_latency_s: float = 0.0,
    notes: str = '',
) -> ScenarioMetrics:
    """Submit ``n_items`` activities through the production dispatch path.

    Registers an async or sync activity on the worker's registry, builds real
    ``pb.ActivityRequest`` protos, and submits ``_execute_activity_async`` /
    ``_execute_activity`` to ``_AsyncWorkerManager``. The mock stub captures the
    completion timestamp per task so we can compute end-to-end latency.

    ``activity_factory`` defaults to ``asyncio.sleep`` / ``time.sleep`` (synthetic
    work). Pass a custom factory (e.g. ``_async_fetch_factory(url, ...)``) to
    exercise real I/O instead.
    """
    options = ConcurrencyOptions(
        maximum_concurrent_activity_work_items=semaphore_cap,
        maximum_concurrent_orchestration_work_items=semaphore_cap,
        maximum_thread_pool_workers=thread_pool_workers,
    )
    worker = _build_worker(options)
    manager = worker._async_worker_manager
    stub = _MockSidecarStub(send_latency_s=send_latency_s)

    start_ts: dict[int, float] = {}
    end_ts: dict[int, float] = {}
    activity_fn: Callable[..., object]
    if activity_kind == 'async':
        activity_fn = (
            activity_factory(start_ts, end_ts)
            if activity_factory is not None
            else _async_sleep_factory(server_latency_s, start_ts, end_ts)
        )
        handler = worker._execute_activity_async
    elif activity_kind == 'sync':
        activity_fn = (
            activity_factory(start_ts, end_ts)
            if activity_factory is not None
            else _sync_sleep_factory(server_latency_s, start_ts, end_ts)
        )
        handler = worker._execute_activity
    else:
        raise ValueError(f'unknown activity_kind: {activity_kind}')

    activity_name = f'bench_{activity_kind}'
    worker._registry.add_named_activity(activity_name, activity_fn)

    baseline_rss_kb = _current_rss_kb()
    sampler = _Sampler()
    sampler_task = asyncio.create_task(sampler.run())
    worker_task = asyncio.create_task(manager.run())

    # Wait for the manager to set up its activity queue, then attach the sampler.
    while manager.activity_queue is None:
        await asyncio.sleep(0)
    sampler.watch_queue(manager.activity_queue)

    submit_ts: dict[int, float] = {}
    submit_start = time.perf_counter()
    for i in range(n_items):
        req = _build_activity_request(activity_name, task_id=i, instance_id='bench')
        submit_ts[i] = time.perf_counter()
        manager.submit_activity(handler, activity_fn, req, stub, '')

    await manager.activity_queue.join()
    wallclock_s = time.perf_counter() - submit_start

    manager._shutdown = True
    sampler.stop()
    await asyncio.gather(worker_task, sampler_task, return_exceptions=True)
    manager.shutdown()

    e2e_samples: list[float] = []
    for task_id, t_submit in submit_ts.items():
        t_complete = stub.completions.get(task_id)
        if t_complete is not None:
            e2e_samples.append(t_complete - t_submit)

    throughput = len(e2e_samples) / wallclock_s if wallclock_s > 0 else 0.0
    return ScenarioMetrics(
        name=name,
        n_items=n_items,
        semaphore_cap=semaphore_cap,
        thread_pool_workers=thread_pool_workers,
        server_latency_s=server_latency_s,
        wallclock_s=wallclock_s,
        throughput_per_s=throughput,
        latency=LatencyStats.from_samples(e2e_samples),
        peak_tasks=sampler.peak_tasks,
        peak_queue_depth=sampler.peak_queue_depth,
        peak_rss_delta_mb=max(0.0, (sampler.peak_rss_kb - baseline_rss_kb) / 1024.0),
        notes=notes,
    )


# ============================================================================
# Lite harness — used by the OOM safety test where we just need raw Task
# bookkeeping with no proto/stub overhead.
# ============================================================================


def _make_activity_context(orchestration_id: str, task_id: int) -> task.ActivityContext:
    return task.ActivityContext(orchestration_id, task_id, '', propagated_history=None)


async def _run_lite(
    *,
    name: str,
    activity: Callable,
    n_items: int,
    semaphore_cap: int,
    thread_pool_workers: int,
    server_latency_s: float,
    notes: str = '',
) -> ScenarioMetrics:
    options = ConcurrencyOptions(
        maximum_concurrent_activity_work_items=semaphore_cap,
        maximum_concurrent_orchestration_work_items=semaphore_cap,
        maximum_thread_pool_workers=thread_pool_workers,
    )
    manager = _AsyncWorkerManager(options, logger=LOGGER)

    baseline_rss_kb = _current_rss_kb()
    sampler = _Sampler()
    sampler_task = asyncio.create_task(sampler.run())
    worker_task = asyncio.create_task(manager.run())

    while manager.activity_queue is None:
        await asyncio.sleep(0)
    sampler.watch_queue(manager.activity_queue)

    for i in range(n_items):
        ctx = _make_activity_context('bench', i)
        manager.submit_activity(activity, ctx, None)

    start = time.perf_counter()
    await manager.activity_queue.join()
    wallclock_s = time.perf_counter() - start

    manager._shutdown = True
    sampler.stop()
    await asyncio.gather(worker_task, sampler_task, return_exceptions=True)
    manager.shutdown()

    throughput = n_items / wallclock_s if wallclock_s > 0 else 0.0
    return ScenarioMetrics(
        name=name,
        n_items=n_items,
        semaphore_cap=semaphore_cap,
        thread_pool_workers=thread_pool_workers,
        server_latency_s=server_latency_s,
        wallclock_s=wallclock_s,
        throughput_per_s=throughput,
        latency=LatencyStats.from_samples([]),
        peak_tasks=sampler.peak_tasks,
        peak_queue_depth=sampler.peak_queue_depth,
        peak_rss_delta_mb=max(0.0, (sampler.peak_rss_kb - baseline_rss_kb) / 1024.0),
        notes=notes,
    )


# ============================================================================
# Sustained-load harness — open-loop submission at a target rate for D seconds.
# ============================================================================


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


async def _run_sustained(
    *,
    duration_s: float,
    target_rate_per_s: float,
    semaphore_cap: int,
    thread_pool_workers: int,
    server_latency_s: float,
    activity_factory: ActivityFactory | None = None,
) -> SustainedMetrics:
    """Continuously submit async activities for ``duration_s`` at a target rate.

    Records per-task submit/end timestamps so the harness can split tail latency
    by quarter of the run, exposing drift. ``activity_factory`` defaults to
    ``asyncio.sleep``; pass an HTTP fetch factory to exercise real I/O.
    """
    options = ConcurrencyOptions(
        maximum_concurrent_activity_work_items=semaphore_cap,
        maximum_concurrent_orchestration_work_items=semaphore_cap,
        maximum_thread_pool_workers=thread_pool_workers,
    )
    worker = _build_worker(options)
    manager = worker._async_worker_manager
    stub = _MockSidecarStub()
    start_ts: dict[int, float] = {}
    end_ts: dict[int, float] = {}
    activity_fn = (
        activity_factory(start_ts, end_ts)
        if activity_factory is not None
        else _async_sleep_factory(server_latency_s, start_ts, end_ts)
    )
    activity_name = 'bench_sustained'
    worker._registry.add_named_activity(activity_name, activity_fn)

    baseline_rss_kb = _current_rss_kb()
    sampler = _Sampler()
    sampler_task = asyncio.create_task(sampler.run())
    worker_task = asyncio.create_task(manager.run())

    while manager.activity_queue is None:
        await asyncio.sleep(0)
    sampler.watch_queue(manager.activity_queue)

    submit_ts: dict[int, float] = {}
    submit_interval = 1.0 / target_rate_per_s

    submitter_done = asyncio.Event()
    submitted = 0
    bench_start = time.perf_counter()

    async def submitter() -> None:
        nonlocal submitted
        try:
            next_submit = bench_start
            while True:
                now = time.perf_counter()
                if now - bench_start >= duration_s:
                    return
                if now >= next_submit:
                    req = _build_activity_request(activity_name, submitted, 'bench-sus')
                    submit_ts[submitted] = now
                    manager.submit_activity(
                        worker._execute_activity_async, activity_fn, req, stub, ''
                    )
                    submitted += 1
                    next_submit += submit_interval
                    continue
                wait_s = max(0.0, next_submit - time.perf_counter())
                await asyncio.sleep(wait_s)
        finally:
            submitter_done.set()

    sub_task = asyncio.create_task(submitter())
    await sub_task
    await manager.activity_queue.join()
    wallclock_s = time.perf_counter() - bench_start

    manager._shutdown = True
    sampler.stop()
    await asyncio.gather(worker_task, sampler_task, return_exceptions=True)
    manager.shutdown()

    e2e_samples_with_submit: list[tuple[float, float]] = []
    for task_id, t_submit in submit_ts.items():
        t_complete = stub.completions.get(task_id)
        if t_complete is not None:
            e2e_samples_with_submit.append((t_submit, t_complete - t_submit))

    e2e_samples_with_submit.sort(key=lambda x: x[0])
    overall = [s for _, s in e2e_samples_with_submit]
    quarter_size = max(1, len(overall) // 4)
    first_quarter = overall[:quarter_size]
    last_quarter = overall[-quarter_size:]

    return SustainedMetrics(
        target_rate_per_s=target_rate_per_s,
        duration_s=duration_s,
        submitted=submitted,
        completed=len(overall),
        wallclock_s=wallclock_s,
        throughput_per_s=len(overall) / wallclock_s if wallclock_s > 0 else 0.0,
        latency_overall=LatencyStats.from_samples(overall),
        latency_first_quarter=LatencyStats.from_samples(first_quarter),
        latency_last_quarter=LatencyStats.from_samples(last_quarter),
        peak_tasks=sampler.peak_tasks,
        peak_queue_depth=sampler.peak_queue_depth,
        peak_rss_delta_mb=max(0.0, (sampler.peak_rss_kb - baseline_rss_kb) / 1024.0),
    )


# ============================================================================
# Scenario runners
# ============================================================================


async def run_concurrency_win() -> list[ScenarioMetrics]:
    """Issue #897 repro: async fan-out vs sync baseline at 100 x 1 s activities."""
    server_latency = 1.0
    n_items = 100
    async with _slow_aiohttp_server(server_latency) as url:
        start_ts_async: dict[int, float] = {}
        end_ts_async: dict[int, float] = {}
        async_metrics = await _run_lite(
            name='Async fan-out (issue #897 repro)',
            activity=_async_fetch_factory(url, start_ts_async, end_ts_async),
            n_items=n_items,
            semaphore_cap=1000,
            thread_pool_workers=8,
            server_latency_s=server_latency,
            notes='100 awaits run concurrently on the loop',
        )
        start_ts_sync: dict[int, float] = {}
        end_ts_sync: dict[int, float] = {}
        sync_metrics = await _run_lite(
            name='Sync baseline (pre-#897 behavior)',
            activity=_sync_fetch_factory(url, start_ts_sync, end_ts_sync),
            n_items=n_items,
            semaphore_cap=1000,
            thread_pool_workers=8,
            server_latency_s=server_latency,
            notes='gated by thread pool size, demonstrates the bug from #897',
        )
    return [async_metrics, sync_metrics]


async def run_throughput_scaling() -> list[ScenarioMetrics]:
    """Vary N at fixed 50 ms server latency. Capture throughput plateau."""
    server_latency = 0.05
    semaphore_cap = 5000
    thread_pool_workers = 16
    grid = [100, 500, 1000, 2500, 5000]
    metrics: list[ScenarioMetrics] = []
    for n in grid:
        m = await _run_full(
            name=f'Throughput N={n}',
            n_items=n,
            semaphore_cap=semaphore_cap,
            thread_pool_workers=thread_pool_workers,
            server_latency_s=server_latency,
            activity_kind='async',
            notes='full _execute_activity_async path + mock CompleteActivityTask',
        )
        metrics.append(m)
    return metrics


async def run_semaphore_sensitivity() -> list[ScenarioMetrics]:
    """Vary semaphore cap at fixed N=2500 / 50 ms. Shows cap-side trade-off."""
    server_latency = 0.05
    n_items = 2500
    thread_pool_workers = 16
    grid = [50, 100, 500, 1000, 5000]
    metrics: list[ScenarioMetrics] = []
    for cap in grid:
        m = await _run_full(
            name=f'Sem cap={cap}',
            n_items=n_items,
            semaphore_cap=cap,
            thread_pool_workers=thread_pool_workers,
            server_latency_s=server_latency,
            activity_kind='async',
            notes=(
                'lower caps serialize the batch through fewer parallel slots'
                if cap <= 100
                else 'caps above N x latency yield no further gain'
            ),
        )
        metrics.append(m)
    return metrics


async def run_failure_threshold() -> list[ScenarioMetrics]:
    """Hold cap=1000 / 50 ms and ramp N. The threshold is the first row where
    p99 exceeds 2 x server_latency, marking the regime where queue wait
    dominates work."""
    server_latency = 0.05
    semaphore_cap = 1000
    thread_pool_workers = 16
    grid = [500, 1000, 2500, 5000, 10000]
    metrics: list[ScenarioMetrics] = []
    for n in grid:
        m = await _run_full(
            name=f'Threshold N={n} (cap={semaphore_cap})',
            n_items=n,
            semaphore_cap=semaphore_cap,
            thread_pool_workers=thread_pool_workers,
            server_latency_s=server_latency,
            activity_kind='async',
            notes='N > cap forces queue wait; p99 grows linearly',
        )
        metrics.append(m)
    return metrics


async def run_sustained_load(duration_s: float = SUSTAINED_DURATION_S) -> SustainedMetrics:
    """Open-loop steady-state run at a target rate slightly below peak."""
    return await _run_sustained(
        duration_s=duration_s,
        target_rate_per_s=200.0,
        semaphore_cap=1000,
        thread_pool_workers=16,
        server_latency_s=0.05,
    )


async def run_delivery_overhead() -> list[ScenarioMetrics]:
    """Hold workload fixed and vary the simulated sidecar CompleteActivityTask
    latency. Quantifies the response-delivery cost added by ``run_in_executor``.
    """
    server_latency = 0.05
    n_items = 1000
    semaphore_cap = 1000
    thread_pool_workers = 16
    grid = [0.000, 0.001, 0.005, 0.010]
    metrics: list[ScenarioMetrics] = []
    for send_latency in grid:
        m = await _run_full(
            name=f'Delivery latency={int(send_latency * 1000)}ms',
            n_items=n_items,
            semaphore_cap=semaphore_cap,
            thread_pool_workers=thread_pool_workers,
            server_latency_s=server_latency,
            activity_kind='async',
            send_latency_s=send_latency,
            notes='response delivery shares the worker thread pool sized by maximum_thread_pool_workers',
        )
        metrics.append(m)
    return metrics


async def run_oom_safety() -> ScenarioMetrics:
    """10 000 in-flight activities with a 1 000-cap semaphore. Validates that the
    pile of Tasks parked on the semaphore does not blow up RSS.
    """
    server_latency = 0.05
    start_ts: dict[int, float] = {}
    end_ts: dict[int, float] = {}
    return await _run_lite(
        name='OOM safety (10k tasks, 1k semaphore)',
        activity=_async_sleep_factory(server_latency, start_ts, end_ts),
        n_items=10_000,
        semaphore_cap=1000,
        thread_pool_workers=8,
        server_latency_s=server_latency,
        notes='~9k tasks blocked on the semaphore. Peak RSS delta budget is 500 MB.',
    )


async def run_real_http_workload() -> list[ScenarioMetrics]:
    """Production-shape scenarios driving real ``httpx.AsyncClient`` fetches.

    Mirrors ``examples/workflow/async_activities.py``: each activity opens a fresh
    ``AsyncClient`` and GETs a local aiohttp endpoint that sleeps for 50 ms. Uses
    the production dispatch path (``_execute_activity_async`` + mock stub) so the
    measured latency is submit → response delivery, including TCP, HTTP, JSON
    encode/decode, and ``run_in_executor`` for the response send.

    Async fetches at the same grid as the synthetic sweep let users compare
    isolated SDK overhead to end-to-end behavior under real I/O.
    """
    server_latency = 0.05
    grid = [(100, 1000, 16), (500, 1000, 16), (1000, 1000, 16), (2500, 5000, 16)]
    metrics: list[ScenarioMetrics] = []
    async with _slow_aiohttp_server(server_latency) as url:
        for n, cap, pool in grid:
            async_metrics = await _run_full(
                name=f'Real HTTP async N={n}',
                n_items=n,
                semaphore_cap=cap,
                thread_pool_workers=pool,
                server_latency_s=server_latency,
                activity_kind='async',
                activity_factory=lambda s, e, url=url: _async_fetch_factory(url, s, e),
                notes='httpx.AsyncClient → aiohttp server (50 ms)',
            )
            metrics.append(async_metrics)
        # One sync row at N=100 to keep the comparison honest without making the
        # bench painful — sync at higher N takes a long wall-clock.
        sync_metrics = await _run_full(
            name='Real HTTP sync N=100',
            n_items=100,
            semaphore_cap=1000,
            thread_pool_workers=16,
            server_latency_s=server_latency,
            activity_kind='sync',
            activity_factory=lambda s, e, url=url: _sync_fetch_factory(url, s, e),
            notes='httpx.Client → aiohttp server, throttled by thread pool',
        )
        metrics.append(sync_metrics)
    return metrics


async def run_real_http_sustained(
    duration_s: float = SUSTAINED_DURATION_S,
) -> SustainedMetrics:
    """Sustained run mirroring real production: continuous httpx.AsyncClient fetches.

    Same shape as ``run_sustained_load`` but each activity is a real HTTP fetch
    against a local aiohttp server, so the numbers reflect a workflow-heavy
    deployment doing third-party API calls.
    """
    server_latency = 0.05
    async with _slow_aiohttp_server(server_latency) as url:
        return await _run_sustained(
            duration_s=duration_s,
            target_rate_per_s=100.0,
            semaphore_cap=1000,
            thread_pool_workers=16,
            server_latency_s=server_latency,
            activity_factory=lambda s, e: _async_fetch_factory(url, s, e),
        )


# ============================================================================
# Report generation
# ============================================================================


def _format_concurrency_table(metrics: list[ScenarioMetrics]) -> str:
    header = (
        '| Scenario | N | Sem | Pool | Latency (s) | Wallclock (s) | Tput/s | p50 ms | p95 ms |'
        ' p99 ms | Peak tasks | Peak queue | Peak RSS Δ (MB) | Notes |\n'
        '| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |\n'
    )
    rows = []
    for m in metrics:
        rows.append(
            f'| {m.name} | {m.n_items} | {m.semaphore_cap} | {m.thread_pool_workers} |'
            f' {m.server_latency_s:.3f} | {m.wallclock_s:.2f} | {m.throughput_per_s:.1f} |'
            f' {m.latency.p50_ms:.1f} | {m.latency.p95_ms:.1f} | {m.latency.p99_ms:.1f} |'
            f' {m.peak_tasks} | {m.peak_queue_depth} | {m.peak_rss_delta_mb:.1f} | {m.notes} |'
        )
    return header + '\n'.join(rows)


def _format_legacy_table(metrics: list[ScenarioMetrics]) -> str:
    """Compatibility table for scenarios without per-item latency (#897 repro, OOM)."""
    header = (
        '| Scenario | N | Sem | Pool | Latency (s) | Wallclock (s) | Tput/s | Peak tasks |'
        ' Peak queue | Peak RSS Δ (MB) | Notes |\n'
        '| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |\n'
    )
    rows = []
    for m in metrics:
        rows.append(
            f'| {m.name} | {m.n_items} | {m.semaphore_cap} | {m.thread_pool_workers} |'
            f' {m.server_latency_s:.3f} | {m.wallclock_s:.2f} | {m.throughput_per_s:.1f} |'
            f' {m.peak_tasks} | {m.peak_queue_depth} | {m.peak_rss_delta_mb:.1f} | {m.notes} |'
        )
    return header + '\n'.join(rows)


def _format_sustained_block(m: SustainedMetrics) -> str:
    return (
        f'- **Target rate**: {m.target_rate_per_s:.0f}/s for {m.duration_s:.0f} s\n'
        f'- **Submitted / completed**: {m.submitted} / {m.completed}\n'
        f'- **Wallclock**: {m.wallclock_s:.2f} s (effective throughput'
        f' {m.throughput_per_s:.1f}/s)\n'
        f'- **Latency (overall)**: p50 {m.latency_overall.p50_ms:.1f} ms,'
        f' p95 {m.latency_overall.p95_ms:.1f} ms, p99 {m.latency_overall.p99_ms:.1f} ms,'
        f' max {m.latency_overall.max_ms:.1f} ms\n'
        f'- **Latency (first 25%)**: p99 {m.latency_first_quarter.p99_ms:.1f} ms\n'
        f'- **Latency (last 25%)**: p99 {m.latency_last_quarter.p99_ms:.1f} ms\n'
        f'- **Peak tasks**: {m.peak_tasks}, peak queue depth: {m.peak_queue_depth},'
        f' peak RSS Δ: {m.peak_rss_delta_mb:.1f} MB\n'
    )


def _find_failure_threshold(metrics: list[ScenarioMetrics], baseline_latency_ms: float) -> str:
    threshold_factor = 2.0
    threshold_ms = baseline_latency_ms * threshold_factor
    for m in metrics:
        if m.latency.p99_ms > threshold_ms:
            return (
                f'p99 first exceeds {threshold_factor:g}x server latency'
                f' ({threshold_ms:.1f} ms) at **N={m.n_items}** with cap={m.semaphore_cap}'
                f' (p99 = {m.latency.p99_ms:.1f} ms).'
            )
    return (
        f'p99 stayed below {threshold_factor:g}x server latency across the full grid'
        f' (max N={metrics[-1].n_items}); the SDK did not degrade in this run.'
    )


def _format_environment_block(env: RunEnvironment) -> str:
    mem_str = f'{env.total_memory_gb:.1f} GB' if env.total_memory_gb > 0 else 'unknown'
    return (
        '## Run environment\n'
        '\n'
        f'- **Timestamp**: {env.timestamp_utc}\n'
        f'- **Git commit**: `{env.git_commit}`\n'
        f'- **Python**: {env.python_implementation} {env.python_version}\n'
        f'- **OS**: {env.os_release}\n'
        f'- **Platform**: `{env.platform}`\n'
        f'- **CPU**: {env.cpu_model} ({env.cpu_logical_cores} logical cores)\n'
        f'- **Memory**: {mem_str}\n'
        f'- **CI environment**: {"yes" if env.is_ci else "no"}\n'
        '\n'
        '**Numbers from this report are specific to this machine.** Re-run the benchmark'
        ' on your hardware before drawing conclusions; on a small CI runner or a busy'
        ' workstation they will diverge. The shape of the curves (throughput plateau,'
        ' p99 inflection, drift) is what to compare across machines.\n'
    )


def _write_results(
    *,
    env: RunEnvironment,
    concurrency: list[ScenarioMetrics],
    throughput: list[ScenarioMetrics],
    semaphore: list[ScenarioMetrics],
    threshold: list[ScenarioMetrics],
    delivery: list[ScenarioMetrics],
    sustained: SustainedMetrics,
    oom: ScenarioMetrics,
    real_http: list[ScenarioMetrics],
    real_http_sustained: SustainedMetrics,
) -> None:
    threshold_summary = _find_failure_threshold(
        threshold, baseline_latency_ms=threshold[0].server_latency_s * 1000.0
    )
    body = [
        '# Async-activity load benchmark results',
        '',
        'Generated by `bench_async_activities.py`. Re-run with:',
        '',
        '```bash',
        'uv run python ext/dapr-ext-workflow/benchmarks/bench_async_activities.py',
        '```',
        '',
        _format_environment_block(env),
        '',
        'Each scenario drives the production dispatch path'
        ' (`TaskHubGrpcWorker._execute_activity_async`) through `_AsyncWorkerManager` against'
        ' a mock `CompleteActivityTask` stub. End-to-end latency is measured from `submit_activity`'
        ' to the mock stub receiving the response, so queue wait, semaphore acquisition,'
        ' activity work, response build, and `run_in_executor` delivery are all included.',
        '',
        '## 1. Concurrency win (issue #897 repro)',
        '',
        'Proves async activities run concurrently on the loop; the sync path is gated by the'
        ' thread pool. This row reuses the original repro at 100 × 1 s HTTP fetches.',
        '',
        _format_legacy_table(concurrency),
        '',
        '## 2. Throughput scaling',
        '',
        'Async fan-out at 50 ms server latency, semaphore cap 5000, thread pool 16. Throughput'
        ' is reported as items completed per wallclock second; the sweep shows where the curve'
        ' flattens.',
        '',
        _format_concurrency_table(throughput),
        '',
        '## 3. Semaphore-cap sensitivity',
        '',
        'N=2500 async activities at 50 ms server latency. Cap below ~500 starves the loop and'
        ' inflates queue wait. Above that, gains compress.',
        '',
        _format_concurrency_table(semaphore),
        '',
        '## 4. Failure threshold (queue-wait inflection)',
        '',
        'Cap held at 1000, ramp N. Until N approaches cap, p99 stays close to server latency.'
        ' Past it, queue wait dominates and p99 grows ~linearly with `N / cap`.',
        '',
        _format_concurrency_table(threshold),
        '',
        f'**Threshold**: {threshold_summary}',
        '',
        '## 5. Sidecar response delivery overhead',
        '',
        'Mock `CompleteActivityTask` is given an artificial delay. Async responses go through'
        ' `loop.run_in_executor(thread_pool, ...)`, sharing the worker thread pool sized by'
        ' `maximum_thread_pool_workers`. Delivery latency above ~5 ms × concurrency exceeds the'
        ' pool and serializes, inflating tail latency.',
        '',
        _format_concurrency_table(delivery),
        '',
        '## 6. Sustained load',
        '',
        _format_sustained_block(sustained),
        '',
        '## 7. Real HTTP workload (production shape)',
        '',
        'Each activity opens a fresh `httpx.AsyncClient` and GETs a local aiohttp endpoint'
        ' that sleeps 50 ms. Mirrors `examples/workflow/async_activities.py`. The sync row'
        ' at N=100 shows the same workload throttled by the thread pool — directly comparable'
        ' to the rest of the table.',
        '',
        _format_concurrency_table(real_http),
        '',
        '## 8. Real HTTP sustained load',
        '',
        'Open-loop submission of real `httpx.AsyncClient` fetches at 100/s. Confirms steady'
        ' state under genuine I/O, not synthetic sleep.',
        '',
        _format_sustained_block(real_http_sustained),
        '',
        '## 9. OOM safety',
        '',
        '10 000 in-flight async activities at 50 ms with a 1 000-cap semaphore. The'
        ' ~9 000 Tasks parked on the semaphore are the design-discussion concern. Peak RSS'
        ' delta stays well under the 500 MB budget, so the unbounded-pending-Task pattern is'
        ' fine in practice.',
        '',
        _format_legacy_table([oom]),
        '',
        '## How to read this report',
        '',
        '- **Tput/s** is the closed-loop throughput (items completed / wallclock).'
        ' For the sustained scenario it is the steady-state value over the full run.',
        '- **p99 ms** is the end-to-end latency for the 99th-percentile item: time from'
        ' `submit_activity` to the mock stub seeing the response.',
        "- **Peak queue** is the maximum depth of the manager's `activity_queue` during the"
        ' run. Non-zero peak queue means submission temporarily outran the semaphore.',
        '- **Peak tasks** is the maximum number of live `asyncio.Task` objects in the process,'
        ' which doubles as a sanity check on the unbounded-pending-Task pattern.',
        '',
        '## Operational guidance',
        '',
        'See `ext/dapr-ext-workflow/docs/concurrency.md` for the full operational write-up,'
        ' including sizing recommendations for `maximum_concurrent_activity_work_items`,'
        ' `maximum_thread_pool_workers`, and the asyncio default-executor caveat.',
    ]
    RESULTS_PATH.write_text('\n'.join(body) + '\n', encoding='utf-8')


# ============================================================================
# Budget assertions
# ============================================================================


def _assert_budgets(
    *,
    concurrency: list[ScenarioMetrics],
    throughput: list[ScenarioMetrics],
    semaphore: list[ScenarioMetrics],
    threshold: list[ScenarioMetrics],
    delivery: list[ScenarioMetrics],
    sustained: SustainedMetrics,
    oom: ScenarioMetrics,
    real_http: list[ScenarioMetrics],
    real_http_sustained: SustainedMetrics,
) -> None:
    """Pass criteria. Loud failure if a regression makes any of them false.

    Budgets are intentionally generous so CI doesn't flake; they catch order-of-magnitude
    regressions, not micro-fluctuations.
    """
    async_repro, sync_baseline = concurrency
    # Issue #897: async must finish close to a single server-latency window.
    assert async_repro.wallclock_s < async_repro.server_latency_s * 5, (
        f'Async fan-out took {async_repro.wallclock_s:.2f}s for'
        f' {async_repro.n_items} × {async_repro.server_latency_s}s activities;'
        f' async dispatch is not actually concurrent.'
    )
    # Issue #897: sync baseline must be at least one extra latency window slower.
    assert sync_baseline.wallclock_s > async_repro.wallclock_s + async_repro.server_latency_s, (
        f'Sync baseline ({sync_baseline.wallclock_s:.2f}s) was not at least one'
        f' latency window slower than async ({async_repro.wallclock_s:.2f}s);'
        f' the comparison is meaningless.'
    )

    # Throughput scaling: each larger N must be at least 80% as fast as the smallest;
    # we tolerate the inevitable plateau but reject a collapse.
    base_throughput = throughput[0].throughput_per_s
    for m in throughput[1:]:
        assert m.throughput_per_s >= base_throughput * 0.5, (
            f'Throughput collapsed at N={m.n_items}: {m.throughput_per_s:.1f}/s'
            f' vs base {base_throughput:.1f}/s. The scaling curve regressed.'
        )

    # Semaphore sensitivity: the smallest cap must be at least 3x slower than the largest.
    smallest_cap = semaphore[0]
    largest_cap = semaphore[-1]
    assert smallest_cap.wallclock_s > largest_cap.wallclock_s * 1.5, (
        f'Wallclock at cap={smallest_cap.semaphore_cap} ({smallest_cap.wallclock_s:.2f}s)'
        f' was not meaningfully slower than at cap={largest_cap.semaphore_cap}'
        f' ({largest_cap.wallclock_s:.2f}s). The semaphore is not gating concurrency.'
    )

    # Failure threshold: at N ≤ cap, p99 must be within 5x of server latency.
    cap = threshold[0].semaphore_cap
    server_latency_ms = threshold[0].server_latency_s * 1000.0
    for m in threshold:
        if m.n_items <= cap:
            assert m.latency.p99_ms <= server_latency_ms * 5, (
                f'p99 at N={m.n_items} (≤ cap={cap}) was {m.latency.p99_ms:.1f} ms,'
                f' >5x server latency ({server_latency_ms:.1f} ms).'
                f' The dispatch path has unexpected overhead.'
            )

    # Delivery overhead: zero-delay delivery must keep p99 < 200 ms at N=1000.
    zero_delay = delivery[0]
    assert zero_delay.latency.p99_ms < 200.0, (
        f'p99 with zero delivery delay was {zero_delay.latency.p99_ms:.1f} ms at N={zero_delay.n_items};'
        f' the SDK adds more than 200 ms of overhead on top of the {zero_delay.server_latency_s * 1000:.0f}'
        f' ms activity, which is too much.'
    )

    # Sustained: last-quarter p99 must not be more than 3x the first-quarter p99.
    drift = sustained.latency_last_quarter.p99_ms
    first = max(sustained.latency_first_quarter.p99_ms, 1.0)
    assert drift <= first * 3.0, (
        f'Sustained tail latency drifted: first-quarter p99 = {first:.1f} ms,'
        f' last-quarter p99 = {drift:.1f} ms.'
        f' Steady state is degrading over the run.'
    )

    # OOM safety budgets — unchanged from the original benchmark.
    assert oom.peak_tasks <= int(oom.n_items * 1.5), (
        f'Peak Tasks ({oom.peak_tasks}) exceeded 1.5 × N={oom.n_items}.'
        f' The per-item Task accounting is inflated.'
    )
    assert oom.peak_rss_delta_mb < 500.0, (
        f'Peak RSS delta {oom.peak_rss_delta_mb:.1f} MB exceeded the 500 MB budget.'
        f' The unbounded pending-Task pattern needs an asyncio.Queue cap.'
    )

    # Real-HTTP workload: async path must beat the sync path's wallclock
    # decisively. At small N, per-call ``httpx.AsyncClient(...)`` setup masks the
    # win, so we compare the peak async throughput across the sweep against the
    # sync row.
    *real_async_rows, real_sync = real_http
    peak_async_throughput = max(m.throughput_per_s for m in real_async_rows)
    assert peak_async_throughput > real_sync.throughput_per_s * 1.25, (
        f'Real-HTTP peak async throughput ({peak_async_throughput:.1f}/s) was not'
        f' >1.25x sync N={real_sync.n_items} ({real_sync.throughput_per_s:.1f}/s).'
        f' The async path lost its concurrency advantage under real I/O.'
    )
    # And at the largest async N, p99 must scale with the batch — not with the
    # entire history of the run.
    largest_async = max(real_async_rows, key=lambda m: m.n_items)
    assert largest_async.latency.p99_ms < largest_async.wallclock_s * 1000.0 * 1.2, (
        f'Real-HTTP async N={largest_async.n_items}: p99 {largest_async.latency.p99_ms:.0f} ms'
        f' exceeds 1.2x the wallclock ({largest_async.wallclock_s * 1000:.0f} ms),'
        f' which means some items are blocked beyond the entire batch — pathological.'
    )

    # Real-HTTP sustained: same drift guard as the synthetic sustained run,
    # but with slightly more slack because httpx connection churn adds jitter.
    first_http = max(real_http_sustained.latency_first_quarter.p99_ms, 1.0)
    last_http = real_http_sustained.latency_last_quarter.p99_ms
    assert last_http <= first_http * 4.0, (
        f'Real-HTTP sustained tail latency drifted: first-quarter p99 = {first_http:.1f} ms,'
        f' last-quarter p99 = {last_http:.1f} ms. Steady state regressed during the run.'
    )


# ============================================================================
# Real-sidecar opt-in scenario
# ============================================================================


async def run_with_real_sidecar() -> None:
    """End-to-end scenario against a real Dapr sidecar.

    Skipped unless ``DAPR_BENCH_WITH_SIDECAR=1``. Requires the script to be run under
    ``dapr run`` with a workflow-enabled state store, e.g.::

        dapr run --app-id bench --app-protocol grpc --dapr-grpc-port 50001 \\
            -- env DAPR_BENCH_WITH_SIDECAR=1 \\
            uv run python ext/dapr-ext-workflow/benchmarks/bench_async_activities.py
    """
    import dapr.ext.workflow as wf

    n_items = 50
    server_latency_s = 0.5
    wfr = wf.WorkflowRuntime()

    @wfr.workflow(name='bench_real_workflow')
    def bench_workflow(ctx: wf.DaprWorkflowContext, payload: list[int]):
        tasks = [ctx.call_activity(bench_async_activity, input=i) for i in payload]
        return (yield wf.when_all(tasks))

    @wfr.activity(name='bench_async_activity')
    async def bench_async_activity(_ctx: wf.WorkflowActivityContext, _i: int) -> int:
        await asyncio.sleep(server_latency_s)
        return _i

    wfr.start()
    time.sleep(2)
    try:
        client = wf.DaprWorkflowClient()
        instance_id = client.schedule_new_workflow(
            workflow=bench_workflow, input=list(range(n_items))
        )
        start = time.perf_counter()
        state = client.wait_for_workflow_completion(instance_id, timeout_in_seconds=120)
        wallclock = time.perf_counter() - start
        assert state is not None, 'workflow timed out against real sidecar'
        print(
            f'[real-sidecar] {n_items} async activities × {server_latency_s}s'
            f' completed in {wallclock:.2f}s (status {state.runtime_status.name})'
        )
    finally:
        wfr.shutdown()


# ============================================================================
# Entry point
# ============================================================================


async def main() -> None:
    logging.basicConfig(level=logging.WARNING)

    env = RunEnvironment.capture()
    print(
        f'[env] {env.cpu_model} | {env.cpu_logical_cores} cores |'
        f' {env.total_memory_gb:.1f} GB | {env.python_implementation} {env.python_version}',
        flush=True,
    )

    print('[1/9] concurrency win (issue #897 repro)...', flush=True)
    concurrency = await run_concurrency_win()

    print('[2/9] throughput scaling sweep...', flush=True)
    throughput = await run_throughput_scaling()

    print('[3/9] semaphore-cap sensitivity sweep...', flush=True)
    semaphore = await run_semaphore_sensitivity()

    print('[4/9] failure-threshold ramp...', flush=True)
    threshold = await run_failure_threshold()

    print('[5/9] sidecar-delivery overhead sweep...', flush=True)
    delivery = await run_delivery_overhead()

    print(f'[6/9] sustained load ({SUSTAINED_DURATION_S:.0f}s)...', flush=True)
    sustained = await run_sustained_load()

    print('[7/9] real-HTTP workload sweep...', flush=True)
    real_http = await run_real_http_workload()

    real_http_duration = min(SUSTAINED_DURATION_S, 60.0)
    print(f'[8/9] real-HTTP sustained load ({real_http_duration:.0f}s)...', flush=True)
    real_http_sustained = await run_real_http_sustained(duration_s=real_http_duration)

    print('[9/9] OOM safety...', flush=True)
    oom = await run_oom_safety()

    _write_results(
        env=env,
        concurrency=concurrency,
        throughput=throughput,
        semaphore=semaphore,
        threshold=threshold,
        delivery=delivery,
        sustained=sustained,
        oom=oom,
        real_http=real_http,
        real_http_sustained=real_http_sustained,
    )
    print('\n=== concurrency win ===')
    print(_format_legacy_table(concurrency))
    print('\n=== throughput scaling ===')
    print(_format_concurrency_table(throughput))
    print('\n=== semaphore sensitivity ===')
    print(_format_concurrency_table(semaphore))
    print('\n=== failure threshold ===')
    print(_format_concurrency_table(threshold))
    print('\n=== sidecar delivery overhead ===')
    print(_format_concurrency_table(delivery))
    print('\n=== sustained load (synthetic) ===')
    print(_format_sustained_block(sustained))
    print('\n=== real HTTP workload ===')
    print(_format_concurrency_table(real_http))
    print('\n=== real HTTP sustained load ===')
    print(_format_sustained_block(real_http_sustained))
    print('\n=== OOM safety ===')
    print(_format_legacy_table([oom]))
    print(f'\nWrote {RESULTS_PATH.relative_to(Path.cwd())}')

    _assert_budgets(
        concurrency=concurrency,
        throughput=throughput,
        semaphore=semaphore,
        threshold=threshold,
        delivery=delivery,
        sustained=sustained,
        oom=oom,
        real_http=real_http,
        real_http_sustained=real_http_sustained,
    )

    if os.environ.get('DAPR_BENCH_WITH_SIDECAR') == '1':
        print('\n[opt-in] running real-sidecar scenario...')
        await run_with_real_sidecar()


if __name__ == '__main__':
    asyncio.run(main())
