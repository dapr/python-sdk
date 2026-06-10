# Concurrency configuration for `dapr-ext-workflow`

Sizing notes for the worker's concurrency knobs.

## Knobs

| Setting | Default | Effect |
| --- | --- | --- |
| `maximum_concurrent_activity_work_items` | `100 × cpu_count` | Async semaphore cap on in-flight activity work items. |
| `maximum_concurrent_orchestration_work_items` | `100 × cpu_count` | Same, for orchestrations. |
| `maximum_thread_pool_workers` | `cpu_count + 4` | Worker thread pool size. Sync activities run on this pool, and async-activity gRPC response sends also borrow a thread from it. |

A `def` activity consumes a semaphore slot **and** a thread pool worker. An
`async def` activity consumes only a semaphore slot.

## Choosing sync vs async

Sync (`def`) activities are fully supported and unchanged: they run on the thread
pool. Keep CPU-bound work sync. An `async def` that burns CPU blocks the event loop
and starves every other activity.

For **I/O-bound** activities (HTTP calls, database queries, anything that waits),
prefer `async def`. A sync activity holds a thread for the whole wait, so concurrency
is capped at the pool size (`cpu_count + 4`); an async activity holds only a semaphore
slot, so in-flight concurrency scales to `maximum_concurrent_activity_work_items`. The
gap widens with fan-out width. If your activities wait on I/O, moving them to `async def`
is the single biggest concurrency win available.

Raising `maximum_thread_pool_workers` lifts the ceiling for a sync I/O activity you can't
convert yet, but threads scale worse than the loop. Each costs stack memory and contends
on the GIL, so the activity semaphore reaches `100 × cpu_count` in flight where a thread
pool that size would not. It buys headroom, not the async ceiling.

Async helps concurrent activities, not sequential chains. A chain of dependent steps
costs the sum of its steps either way, sync or async.

## Sizing the activity cap

The cap is the lever for throughput and queue wait. Below the cap, in-flight work
runs concurrently; past it, submissions wait in the queue. Rule of thumb: set the
cap to ~2x the expected steady-state in-flight count to absorb bursts.

If activities call a downstream with a hard concurrency limit (e.g. a database
with a 100-connection pool), set the cap below that limit so it doubles as
backpressure.

## Sizing the thread pool

The worker thread pool, sized by `maximum_thread_pool_workers`, has two uses.

**Sync activity execution.** Each `def` activity holds one thread for its
duration. Size to peak concurrent sync-activity count.

**Async response delivery.** Each async activity, on completion, schedules
`stub.CompleteActivityTask` on the same pool to avoid blocking the loop during
the gRPC send. If the sidecar takes >5 ms to acknowledge and the worker runs
many concurrent async activities, response delivery can serialize through the
pool and tail latency inflates. Raise `maximum_thread_pool_workers` to widen
response-delivery throughput.

Mixed workloads with long-running sync activities can starve async response
delivery (and vice versa) since they share the pool. If that becomes an issue,
size `maximum_thread_pool_workers` to the sum of peak sync activity concurrency
and peak in-flight async response sends.

This thread hop goes away when the worker migrates to `grpc.aio`.

## Reusing clients in async activities

When async activities call out over the network (HTTP, a database), a fresh client per
call bounds throughput by connection setup, not the I/O. A per-call `httpx.AsyncClient`
plateaus around a few hundred req/s. Reuse one client and size its pool to the activity
cap:

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
