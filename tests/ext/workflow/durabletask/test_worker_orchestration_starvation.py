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

"""An activity that schedules a workflow waits until the sidecar reports that
workflow started, which needs the new workflow's orchestration work item to run
on this worker. Activities holding every pool thread must not stop it."""

import asyncio
import logging
import threading

from dapr.ext.workflow._durabletask.worker import ConcurrencyOptions, _AsyncWorkerManager


def test_orchestration_runs_while_activities_hold_every_pool_thread() -> None:
    manager = _AsyncWorkerManager(
        ConcurrencyOptions(maximum_thread_pool_workers=2), logger=logging.getLogger()
    )
    child_started = threading.Event()
    activities_running = threading.Barrier(3)

    def activity_waiting_for_child() -> None:
        activities_running.wait(timeout=5)
        child_started.wait(timeout=5)

    def child_orchestration() -> None:
        child_started.set()

    async def scenario() -> bool:
        runner = asyncio.create_task(manager.run())
        manager.submit_activity(activity_waiting_for_child)
        manager.submit_activity(activity_waiting_for_child)
        # Both pool threads are held before the orchestration is submitted.
        await asyncio.to_thread(activities_running.wait, 5)
        manager.submit_orchestration(child_orchestration)
        started = await asyncio.to_thread(child_started.wait, 3)
        manager._shutdown = True
        await runner
        return started

    try:
        assert asyncio.run(scenario()), 'orchestration starved by blocked activities'
    finally:
        manager.shutdown()
