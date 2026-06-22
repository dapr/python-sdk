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

"""Perf regression test for the async activity dispatch path.

Drives ``_execute_activity_async`` through ``_AsyncWorkerManager`` against an in-process
stub. A timeout fails the batch if async activities serialize instead of overlapping.
"""

import asyncio

import dapr.ext.workflow._durabletask.internal.protos as pb
import pytest
from dapr.ext.workflow._durabletask.worker import ConcurrencyOptions, TaskHubGrpcWorker

pytestmark = pytest.mark.perf

ACTIVITY_DURATION_SECONDS = 0.02
N_ITEMS = 1000
SEMAPHORE_CAP = 2000
THREAD_POOL = 16

# Generous fraction of the time to run 1000 activities serially. Should trip fast if async I/O serializes
TIMEOUT_S = 2.0


class _MockSidecarStub:
    """In-process stand-in for the gRPC stub; records activity completions."""

    def __init__(self) -> None:
        self.completions = 0

    def CompleteActivityTask(self, _response: pb.ActivityResponse) -> None:  # noqa: N802
        self.completions += 1


def _activity_request(task_id: int) -> pb.ActivityRequest:
    return pb.ActivityRequest(
        name='regression_async',
        taskId=task_id,
        workflowInstance=pb.WorkflowInstance(instanceId='regression'),
        parentTraceContext=pb.TraceContext(traceParent=''),
        taskExecutionId='',
    )


async def _run_async_batch(n_items: int, timeout_s: float) -> int:
    """Submit ``n_items`` async sleep activities through the dispatch path and drain them.

    Raises ``asyncio.TimeoutError`` if the batch does not drain within ``timeout_s``.
    """
    options = ConcurrencyOptions(
        maximum_concurrent_activity_work_items=SEMAPHORE_CAP,
        maximum_concurrent_orchestration_work_items=SEMAPHORE_CAP,
        maximum_thread_pool_workers=THREAD_POOL,
    )
    worker = TaskHubGrpcWorker(host_address='in-process-mock', concurrency_options=options)
    manager = worker._async_worker_manager
    stub = _MockSidecarStub()

    async def activity(ctx, _inp) -> None:
        await asyncio.sleep(ACTIVITY_DURATION_SECONDS)

    worker_task = asyncio.create_task(manager.run())
    # Non-blocking poll: yield to the event loop until the worker creates the activity queue
    while manager.activity_queue is None:
        await asyncio.sleep(0)
    try:
        for task_id in range(n_items):
            req = _activity_request(task_id)
            manager.submit_activity(worker._execute_activity_async, activity, req, stub, '')
        await asyncio.wait_for(manager.activity_queue.join(), timeout=timeout_s)
    finally:
        manager._shutdown = True
        worker_task.cancel()
        await asyncio.gather(worker_task, return_exceptions=True)
        manager.shutdown()

    return stub.completions


def test_async_activities_overlap_instead_of_serializing():
    """A batch of async activities drains in ~one I/O window, not N of them.

    Fails if the batch cannot finish within ``TIMEOUT_S``, meaning the async path is
    serializing instead of overlapping I/O on the event loop.
    """
    try:
        completions = asyncio.run(_run_async_batch(N_ITEMS, TIMEOUT_S))
    except asyncio.TimeoutError:
        serial_s = N_ITEMS * ACTIVITY_DURATION_SECONDS
        pytest.fail(
            f'{N_ITEMS} async activities did not drain within {TIMEOUT_S:.1f}s. Serialized'
            f' they would cost ~{serial_s:.0f}s, so the async path is not overlapping I/O.'
        )
    assert completions == N_ITEMS, f'only {completions}/{N_ITEMS} activities completed'
