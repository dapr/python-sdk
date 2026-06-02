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

"""Sync-vs-async activity benchmarks for ``dapr-ext-workflow``.

Runs the same I/O-bound activity workload as ``def`` and ``async def`` through the
production dispatch path against a mock sidecar stub. Scenarios: a fan-out burst, a
fan-out shaped as many small workflows, and a sustained open-loop run.

Run:

    uv run python ext/dapr-ext-workflow/benchmarks/bench_async_activities.py

``DAPR_BENCH_ACTIVITY_MS`` overrides the activity duration, ``DAPR_BENCH_SUSTAINED_SECONDS``
the sustained run. Writes ``benchmarks/RESULTS.md`` and asserts pass-criteria budgets.
"""

from __future__ import annotations

import asyncio
import logging
import os
from pathlib import Path

from _report import (
    RunEnvironment,
    _format_comparison_table,
    _format_environment_block,
    _format_sustained_table,
)
from dapr.ext.workflow._bench_harness import (
    ScenarioMetrics,
    SustainedMetrics,
    _async_payload_factory,
    _async_sleep_factory,
    _run_full,
    _run_lite,
    _run_sustained,
    _sync_payload_factory,
)

RESULTS_PATH = Path(__file__).parent / 'RESULTS.md'
SUSTAINED_DURATION_S = float(os.environ.get('DAPR_BENCH_SUSTAINED_SECONDS', '120'))
ACTIVITY_LATENCY_S = float(os.environ.get('DAPR_BENCH_ACTIVITY_MS', '200')) / 1000.0

ACTIVITY_GRID = (10, 100, 1000)
WF_ACTIVITY_GRID = (10, 100, 1000)
ACTIVITIES_PER_WORKFLOW = 3
FIXED_PAYLOAD_BYTES = 10 * 1024
PAYLOAD_WORKFLOWS = 100
PAYLOAD_GRID = (('1KB', 1024), ('100KB', 100 * 1024), ('1MB', 1024 * 1024))
WF_IO_S = 0.05
_THREAD_POOL = 16
_SEMAPHORE_CAP = 1200

Row = tuple[str, ScenarioMetrics, ScenarioMetrics]


def _sustained_rate() -> float:
    """Arrival rate just above the sync ceiling (pool / latency)."""
    return round((_THREAD_POOL / ACTIVITY_LATENCY_S) * 1.25)


async def _run(kind: str, n_items: int) -> ScenarioMetrics:
    return await _run_full(
        name=f'{kind} {n_items}',
        n_items=n_items,
        semaphore_cap=_SEMAPHORE_CAP,
        thread_pool_workers=_THREAD_POOL,
        server_latency_s=ACTIVITY_LATENCY_S,
        activity_kind=kind,
    )


async def _fanout_pair(label: str, n_items: int) -> Row:
    return label, await _run('sync', n_items), await _run('async', n_items)


async def run_fanout() -> list[Row]:
    """One workflow fanning out a varying number of activities, sync vs async."""
    return [await _fanout_pair(str(a), a) for a in ACTIVITY_GRID]


async def _workflow_pair(label: str, n_items: int, payload_bytes: int) -> Row:
    """Sync vs async: ``n_items`` sleep activities, each carrying a ``payload_bytes`` payload."""
    sync_m = await _run_full(
        name=f'sync {label}',
        n_items=n_items,
        semaphore_cap=_SEMAPHORE_CAP,
        thread_pool_workers=_THREAD_POOL,
        server_latency_s=WF_IO_S,
        activity_kind='sync',
        activity_factory=lambda s, e: _sync_payload_factory(WF_IO_S, payload_bytes, s, e),
        input_bytes=payload_bytes,
    )
    async_m = await _run_full(
        name=f'async {label}',
        n_items=n_items,
        semaphore_cap=_SEMAPHORE_CAP,
        thread_pool_workers=_THREAD_POOL,
        server_latency_s=WF_IO_S,
        activity_kind='async',
        activity_factory=lambda s, e: _async_payload_factory(WF_IO_S, payload_bytes, s, e),
        input_bytes=payload_bytes,
    )
    return label, sync_m, async_m


async def run_by_payload() -> list[Row]:
    """Fixed workflows x activities, varying payload size."""
    n_items = PAYLOAD_WORKFLOWS * ACTIVITIES_PER_WORKFLOW
    return [await _workflow_pair(label, n_items, size) for label, size in PAYLOAD_GRID]


async def run_by_scale() -> list[Row]:
    """Varying workflows x activities, fixed payload size."""
    rows: list[Row] = []
    for w in WF_ACTIVITY_GRID:
        label = f'{w} × {ACTIVITIES_PER_WORKFLOW}'
        rows.append(await _workflow_pair(label, w * ACTIVITIES_PER_WORKFLOW, FIXED_PAYLOAD_BYTES))
    return rows


async def run_sustained() -> tuple[SustainedMetrics, SustainedMetrics]:
    """Open-loop arrival above the sync ceiling, sync vs async."""
    rate = _sustained_rate()
    sync_m = await _run_sustained(
        duration_s=SUSTAINED_DURATION_S,
        target_rate_per_s=rate,
        semaphore_cap=_SEMAPHORE_CAP,
        thread_pool_workers=_THREAD_POOL,
        server_latency_s=ACTIVITY_LATENCY_S,
        activity_kind='sync',
    )
    async_m = await _run_sustained(
        duration_s=SUSTAINED_DURATION_S,
        target_rate_per_s=rate,
        semaphore_cap=_SEMAPHORE_CAP,
        thread_pool_workers=_THREAD_POOL,
        server_latency_s=ACTIVITY_LATENCY_S,
        activity_kind='async',
    )
    return sync_m, async_m


async def _run_semaphore_gate() -> ScenarioMetrics:
    """Async fan-out behind a small semaphore, to confirm the cap still gates."""
    return await _run_full(
        name='semaphore gate',
        n_items=1000,
        semaphore_cap=50,
        thread_pool_workers=_THREAD_POOL,
        server_latency_s=ACTIVITY_LATENCY_S,
        activity_kind='async',
    )


async def _run_oom_safety() -> ScenarioMetrics:
    """10k async activities behind a 1k semaphore, checking parked Tasks don't blow RSS."""
    return await _run_lite(
        name='oom safety',
        activity=_async_sleep_factory(ACTIVITY_LATENCY_S, {}, {}),
        n_items=10_000,
        semaphore_cap=1000,
        thread_pool_workers=_THREAD_POOL,
        server_latency_s=ACTIVITY_LATENCY_S,
    )


def _write_results(
    *,
    env: RunEnvironment,
    fanout: list[Row],
    by_payload: list[Row],
    by_scale: list[Row],
    sustained: tuple[SustainedMetrics, SustainedMetrics],
) -> None:
    sustained_sync, sustained_async = sustained
    rate = _sustained_rate()
    ceiling = _THREAD_POOL / ACTIVITY_LATENCY_S
    latency_ms = ACTIVITY_LATENCY_S * 1000
    fixed_kb = FIXED_PAYLOAD_BYTES // 1024
    report = f"""
# Sync vs async activity benchmark

Generated by `bench_async_activities.py`. Re-run with:

```bash
uv run python ext/dapr-ext-workflow/benchmarks/bench_async_activities.py
```

{_format_environment_block(env)}

Each I/O activity is a {latency_ms:.0f} ms wait. A `def` activity holds a worker thread for that wait, so the sync path runs at most {_THREAD_POOL} at a time (~{ceiling:.0f}/s); an `async def` activity holds only an event-loop slot, so the waits overlap.

## 1. Fan-out (one workflow)

One workflow fans out a batch of activities at once. Below the thread pool the paths match; above it the sync path serializes and the gap grows with the batch size.

{_format_comparison_table(fanout, key_label='Activities')}

## 2. Workflows: all sync vs all async

Each workflow runs {ACTIVITIES_PER_WORKFLOW} activities (a fan-out and its fan-in aggregator), all the same kind, a sleep carrying a payload. The sync column runs them on the thread pool, the async column on the event loop. A row labeled `{PAYLOAD_WORKFLOWS} × {ACTIVITIES_PER_WORKFLOW}` is {PAYLOAD_WORKFLOWS} workflows of {ACTIVITIES_PER_WORKFLOW} activities each.

### 2a. Varying workflows × activities (fixed {fixed_kb}KB payload)

Scaling the workflow count. The async advantage widens with the count, since the sync path is still capped by the thread pool while the async path keeps overlapping.

{_format_comparison_table(by_scale, key_label='Workflows × activities')}

### 2b. Varying payload (fixed {PAYLOAD_WORKFLOWS} workflows × {ACTIVITIES_PER_WORKFLOW} activities)

Each activity receives and returns a payload of the given size. Async still wins because the waits overlap, but the win narrows and RAM climbs as the payload grows. Every in-flight activity holds its input and output, and JSON ser/deser runs on the loop. RAM is the async run, which holds the most in flight at once.

{_format_comparison_table(by_payload, key_label='Payload', show_async_rss=True)}

## 3. Sustained arrival

Open-loop submission at {rate:.0f}/s, above the ~{ceiling:.0f}/s sync ceiling. The sync path falls behind and its latency drifts upward across the run; the async path holds steady. Compare the first-quarter and last-quarter p99.

{_format_sustained_table(sustained_sync, sustained_async)}

See `ext/dapr-ext-workflow/docs/concurrency.md` for sizing guidance.
"""
    RESULTS_PATH.write_text(report, encoding='utf-8')


def _assert_budgets(
    *,
    fanout: list[Row],
    by_payload: list[Row],
    by_scale: list[Row],
    sustained: tuple[SustainedMetrics, SustainedMetrics],
    semaphore_gate: ScenarioMetrics,
    oom: ScenarioMetrics,
) -> None:
    """Pass criteria. Generous bounds: catch order-of-magnitude regressions, not jitter."""
    _, sync_big, async_big = fanout[-1]
    assert async_big.wallclock_s < ACTIVITY_LATENCY_S * 8, (
        f'Async fan-out N={async_big.n_items} took {async_big.wallclock_s:.2f}s for'
        f' {ACTIVITY_LATENCY_S}s activities; async is not overlapping I/O.'
    )
    assert async_big.wallclock_s * 3.0 < sync_big.wallclock_s, (
        f'Fan-out N={async_big.n_items}: async {async_big.wallclock_s:.2f}s not 3x faster'
        f' than sync {sync_big.wallclock_s:.2f}s.'
    )

    # At the largest scale, async clears the workflows far faster than sync.
    _, scale_sync, scale_async = by_scale[-1]
    assert scale_async.wallclock_s * 3.0 < scale_sync.wallclock_s, (
        f'Scale sweep: async {scale_async.wallclock_s:.2f}s not 3x faster than sync'
        f' {scale_sync.wallclock_s:.2f}s.'
    )

    # Async still beats sync at the largest payload, even as the gap narrows.
    _, pay_sync, pay_async = by_payload[-1]
    assert pay_async.wallclock_s < pay_sync.wallclock_s, (
        f'Payload sweep: async {pay_async.wallclock_s:.2f}s was not faster than sync'
        f' {pay_sync.wallclock_s:.2f}s at the largest payload.'
    )

    sustained_sync, sustained_async = sustained
    async_first = max(sustained_async.latency_first_quarter.p99_ms, 1.0)
    async_last = sustained_async.latency_last_quarter.p99_ms
    assert async_last <= async_first * 3.0, (
        f'Async sustained tail drifted: first-quarter p99 {async_first:.0f} ms,'
        f' last-quarter p99 {async_last:.0f} ms.'
    )
    sync_first = max(sustained_sync.latency_first_quarter.p99_ms, 1.0)
    sync_last = sustained_sync.latency_last_quarter.p99_ms
    assert sync_last > sync_first * 2.0, (
        f'Sync sustained tail did not drift: first-quarter p99 {sync_first:.0f} ms,'
        f' last-quarter p99 {sync_last:.0f} ms.'
    )
    assert sync_last > async_last * 3.0, (
        f'Sync last-quarter p99 ({sync_last:.0f} ms) not >3x async ({async_last:.0f} ms).'
    )

    assert semaphore_gate.wallclock_s > async_big.wallclock_s * 3.0, (
        f'Semaphore did not gate: capped async {semaphore_gate.wallclock_s:.2f}s not'
        f' meaningfully slower than ungated {async_big.wallclock_s:.2f}s.'
    )

    assert oom.peak_tasks <= int(oom.n_items * 1.5), (
        f'Peak Tasks ({oom.peak_tasks}) exceeded 1.5x N={oom.n_items}.'
    )
    assert oom.peak_rss_delta_mb < 500.0, (
        f'Peak RSS delta {oom.peak_rss_delta_mb:.1f} MB exceeded the 500 MB budget.'
    )


async def main() -> None:
    logging.basicConfig(level=logging.WARNING)
    env = RunEnvironment.capture()
    print(
        f'[env] {env.cpu_model} | {env.cpu_logical_cores} cores |'
        f' {env.python_implementation} {env.python_version}',
        flush=True,
    )

    print('[1/4] fan-out (one workflow) sync vs async...', flush=True)
    fanout = await run_fanout()

    print('[2/4] workflows all sync vs all async (payload and scale sweeps)...', flush=True)
    by_payload = await run_by_payload()
    by_scale = await run_by_scale()

    print(f'[3/4] sustained sync vs async ({SUSTAINED_DURATION_S:.0f}s each)...', flush=True)
    sustained = await run_sustained()

    print('[4/4] hidden regression checks...', flush=True)
    semaphore_gate = await _run_semaphore_gate()
    oom = await _run_oom_safety()

    _write_results(
        env=env,
        fanout=fanout,
        by_payload=by_payload,
        by_scale=by_scale,
        sustained=sustained,
    )
    print('\n=== fan-out (one workflow) ===')
    print(_format_comparison_table(fanout, key_label='Activities'))
    print('\n=== 2a. varying workflows × activities ===')
    print(_format_comparison_table(by_scale, key_label='Workflows × activities'))
    print('\n=== 2b. varying payload ===')
    print(_format_comparison_table(by_payload, key_label='Payload', show_async_rss=True))
    print('\n=== sustained ===')
    print(_format_sustained_table(sustained[0], sustained[1]))
    print(f'\nWrote {RESULTS_PATH.relative_to(Path.cwd())}')

    _assert_budgets(
        fanout=fanout,
        by_payload=by_payload,
        by_scale=by_scale,
        sustained=sustained,
        semaphore_gate=semaphore_gate,
        oom=oom,
    )


if __name__ == '__main__':
    asyncio.run(main())
