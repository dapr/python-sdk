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

"""Contract tests for the activity dispatch handlers on ``TaskHubGrpcWorker``.

The work-item dispatcher at the top of ``worker.py``'s gRPC loop selects between
``_execute_activity`` (sync, runs in the thread pool) and ``_execute_activity_async``
(coroutine, awaited on the event loop) using ``inspect.iscoroutinefunction(handler)``
via ``_AsyncWorkerManager._run_func``. These tests pin the async-ness of each handler so
the dispatch routing stays correct.
"""

import asyncio
import inspect
import logging
import threading
from typing import Iterator

import pytest
from dapr.ext.workflow._durabletask.worker import (
    ConcurrencyOptions,
    TaskHubGrpcWorker,
    _AsyncWorkerManager,
)


@pytest.fixture
def worker() -> Iterator[TaskHubGrpcWorker]:
    instance = TaskHubGrpcWorker()
    try:
        yield instance
    finally:
        # The worker was never started, so ``stop()`` early-returns; shut the manager
        # down directly so the test doesn't leak threads if any work was submitted.
        instance.stop()
        instance._async_worker_manager.shutdown()


@pytest.fixture
def manager() -> Iterator[_AsyncWorkerManager]:
    instance = _AsyncWorkerManager(ConcurrencyOptions(), logger=logging.getLogger())
    try:
        yield instance
    finally:
        instance.shutdown()


def test_sync_activity_handler_is_not_a_coroutine_function(worker: TaskHubGrpcWorker):
    assert not inspect.iscoroutinefunction(worker._execute_activity)


def test_async_activity_handler_is_a_coroutine_function(worker: TaskHubGrpcWorker):
    assert inspect.iscoroutinefunction(worker._execute_activity_async)


def test_run_func_awaits_coroutines_directly(manager: _AsyncWorkerManager):
    """``_AsyncWorkerManager._run_func`` is the single point that branches on async-ness.

    A coroutine handler returns its value without going through the thread pool.
    """

    async def coroutine_handler(value: int) -> int:
        return value + 1

    async def driver() -> int:
        return await manager._run_func(coroutine_handler, 41)

    assert asyncio.run(driver()) == 42


def test_run_func_dispatches_sync_callables_to_thread_pool(manager: _AsyncWorkerManager):
    main_thread_id = threading.get_ident()
    captured: dict[str, int] = {}

    def sync_handler(value: int) -> int:
        captured['thread_id'] = threading.get_ident()
        return value + 1

    async def driver() -> int:
        return await manager._run_func(sync_handler, 41)

    result = asyncio.run(driver())
    assert result == 42
    assert captured['thread_id'] != main_thread_id
