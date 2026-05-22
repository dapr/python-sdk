# Concurrency configuration for `dapr-ext-workflow`

Sizing notes for the worker's concurrency knobs. Numbers come from
`benchmarks/bench_async_activities.py`. Re-run it on local hardware to validate.

## Knobs

| Setting | Default | Effect |
| --- | --- | --- |
| `maximum_concurrent_activity_work_items` | `100 × cpu_count` | Async semaphore cap on in-flight activity work items. |
| `maximum_concurrent_orchestration_work_items` | `100 × cpu_count` | Same, for orchestrations. |
| `maximum_thread_pool_workers` | `cpu_count + 4` | Thread pool size for **sync** activities. Async activities run as coroutines on the event loop and never enter this pool. |

A `def` activity consumes a semaphore slot **and** a thread pool worker. An
`async def` activity consumes only a semaphore slot.

## Sizing the activity cap

The cap is the lever for throughput and queue wait. Throughput plateaus around
`cap ≈ peak_in_flight`. Past the cap, queue wait grows linearly. The benchmark's
failure-threshold sweep shows the inflection point clearly. Rule of thumb: set
the cap to ~2x the expected steady-state in-flight count to absorb bursts.

If activities call a downstream with a hard concurrency limit (e.g. a database
with a 100-connection pool), set the cap below that limit so it doubles as
backpressure.

## Sizing the thread pool

Two distinct uses of threads exist.

**Sync activity execution.** Each `def` activity holds one thread for its
duration. Size to peak concurrent sync-activity count.

**Async response delivery.** Each async activity, on completion, schedules
`stub.CompleteActivityTask` via `loop.run_in_executor(None, ...)`. That uses
asyncio's **default executor**, which is process-wide and sized to
`min(32, cpu_count + 4)`. It is *not* `maximum_thread_pool_workers`.

If the sidecar takes >5 ms to acknowledge and the worker runs >30 concurrent
async activities, response delivery serializes through the default executor and
tail latency inflates. Install a larger default executor before starting:

```python
import asyncio
from concurrent.futures import ThreadPoolExecutor

asyncio.get_event_loop().set_default_executor(ThreadPoolExecutor(max_workers=200))
```

This goes away when the worker migrates to `grpc.aio`. Until then, the default
executor is a separate knob from `maximum_thread_pool_workers`.

## Sharing httpx clients

The pattern in `examples/workflow/async_activities.py` opens a fresh
`httpx.AsyncClient` per activity. Correct for most workloads, but each call pays
TCP + TLS setup, and throughput plateaus around a few hundred req/s.

For higher throughput, share a single client across activities:

```python
_shared_client: httpx.AsyncClient | None = None

def _get_client() -> httpx.AsyncClient:
    global _shared_client
    if _shared_client is None:
        _shared_client = httpx.AsyncClient(timeout=30.0)
    return _shared_client
```

The caller owns closing it during worker shutdown. For activities that hit many
hosts or need per-call timeout isolation, stick with per-call clients.

## Re-running the benchmark

```bash
uv run python ext/dapr-ext-workflow/benchmarks/bench_async_activities.py
```

Override the 120 s sustained run with `DAPR_BENCH_SUSTAINED_SECONDS=30` for a
faster local check. Set `DAPR_BENCH_WITH_SIDECAR=1` to exercise the end-to-end
path against a real sidecar. Results land in `RESULTS.md`.
