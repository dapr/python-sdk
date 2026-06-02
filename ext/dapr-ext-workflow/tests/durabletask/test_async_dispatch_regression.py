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

"""Perf regression tests for the async activity dispatch path.

Reuses the benchmark harness (``dapr.ext.workflow._bench_harness``) with small, fast
parameters and asserts machine-independent ratios rather than absolute times, so the
checks stay deterministic in CI. Marked ``perf`` so constrained runners can skip them.
"""

import asyncio

import pytest
from dapr.ext.workflow._bench_harness import (
    _async_sleep_factory,
    _run_full,
    _run_lite,
    _run_sustained,
)

pytestmark = pytest.mark.perf

ACTIVITY_S = 0.02
POOL = 16
SEM = 1000
REPEAT = 2


async def fastest(**kwargs):
    """Fastest of REPEAT sequential runs, so spotty CI noise on one run can't flake the
    wallclock comparisons. Noise only adds time, so the min is the least-disturbed sample.
    """
    runs = [await _run_full(**kwargs) for _ in range(REPEAT)]
    return min(runs, key=lambda m: m.wallclock_s)


def test_async_fan_out_overlaps_and_beats_sync():
    """Async clears a batch in ~one I/O window; sync serializes through the pool."""

    async def run():
        kwargs = dict(
            n_items=300,
            semaphore_cap=SEM,
            thread_pool_workers=POOL,
            server_latency_s=ACTIVITY_S,
        )
        sync_m = await fastest(name='sync', activity_kind='sync', **kwargs)
        async_m = await fastest(name='async', activity_kind='async', **kwargs)
        return sync_m, async_m

    sync_m, async_m = asyncio.run(run())
    assert async_m.wallclock_s < ACTIVITY_S * 20, 'async did not overlap I/O'
    assert async_m.wallclock_s * 2 < sync_m.wallclock_s, 'async did not beat sync at scale'


def test_semaphore_caps_async_concurrency():
    """A small semaphore must gate the async path even though it never touches the pool."""

    async def run():
        kwargs = dict(
            n_items=1000,
            thread_pool_workers=POOL,
            server_latency_s=ACTIVITY_S,
            activity_kind='async',
        )
        gated = await fastest(name='gated', semaphore_cap=10, **kwargs)
        ungated = await fastest(name='ungated', semaphore_cap=SEM, **kwargs)
        return gated, ungated

    gated, ungated = asyncio.run(run())
    assert gated.wallclock_s > ungated.wallclock_s * 2, 'semaphore did not gate concurrency'


def test_sustained_async_holds_while_sync_drifts():
    """Above the sync ceiling, sync tail latency drifts upward and ends far worse than async."""

    async def run():
        kwargs = dict(
            duration_s=3.0,
            target_rate_per_s=1000.0,
            semaphore_cap=SEM,
            thread_pool_workers=POOL,
            server_latency_s=ACTIVITY_S,
        )
        sync_m = await _run_sustained(activity_kind='sync', **kwargs)
        async_m = await _run_sustained(activity_kind='async', **kwargs)
        return sync_m, async_m

    sync_m, async_m = asyncio.run(run())
    sync_first = max(sync_m.latency_first_quarter.p99_ms, 1.0)
    assert sync_m.latency_last_quarter.p99_ms > sync_first * 2, 'sync tail did not drift'
    assert sync_m.latency_last_quarter.p99_ms > async_m.latency_last_quarter.p99_ms * 2


def test_pending_tasks_stay_bounded():
    """Activities parked on the semaphore must not inflate task count or RSS."""

    async def run():
        return await _run_lite(
            name='oom',
            activity=_async_sleep_factory(ACTIVITY_S, {}, {}),
            n_items=2000,
            semaphore_cap=500,
            thread_pool_workers=POOL,
            server_latency_s=ACTIVITY_S,
        )

    metrics = asyncio.run(run())
    assert metrics.peak_tasks <= int(metrics.n_items * 1.5), 'task accounting inflated'
    assert metrics.peak_rss_delta_mb < 500.0, 'RSS exceeded budget'
