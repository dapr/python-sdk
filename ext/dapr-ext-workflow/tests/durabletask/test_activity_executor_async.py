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

"""Unit tests for the async branch of ``_ActivityExecutor``.

These mirror ``test_activity_executor.py`` but exercise the ``execute_async`` path used
when a registered activity is a coroutine function.
"""

import asyncio
import inspect
import json
import logging
from typing import Any

import pytest
from dapr.ext.workflow._durabletask import task, worker

logging.basicConfig(
    format='%(asctime)s.%(msecs)03d %(name)s %(levelname)s: %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
    level=logging.DEBUG,
)
TEST_LOGGER = logging.getLogger('tests')
TEST_INSTANCE_ID = 'abc123'
TEST_TASK_ID = 42


def _get_activity_executor(fn: task.Activity) -> tuple[worker._ActivityExecutor, str]:
    registry = worker._Registry()
    name = registry.add_activity(fn)
    executor = worker._ActivityExecutor(TEST_LOGGER)
    return executor, name


def test_async_activity_inputs():
    """Validates that execute_async awaits the activity and returns the encoded result."""

    async def test_async_activity(ctx: task.ActivityContext, test_input: Any):
        await asyncio.sleep(0)
        return test_input, ctx.orchestration_id, ctx.task_id

    activity_input = 'Hello, 世界!'
    executor, name = _get_activity_executor(test_async_activity)
    result = asyncio.run(
        executor.execute_async(
            test_async_activity,
            TEST_INSTANCE_ID,
            name,
            TEST_TASK_ID,
            json.dumps(activity_input),
        )
    )
    assert result is not None

    result_input, result_orchestration_id, result_task_id = json.loads(result)
    assert activity_input == result_input
    assert TEST_INSTANCE_ID == result_orchestration_id
    assert TEST_TASK_ID == result_task_id


def test_async_activity_exception_propagates():
    async def test_async_activity(ctx: task.ActivityContext, _):
        raise RuntimeError('boom')

    executor, name = _get_activity_executor(test_async_activity)

    with pytest.raises(RuntimeError) as exc_info:
        asyncio.run(
            executor.execute_async(test_async_activity, TEST_INSTANCE_ID, name, TEST_TASK_ID, None)
        )
    assert 'boom' in str(exc_info.value)


def test_async_activity_registry_preserves_coroutine_function():
    """The dispatcher relies on iscoroutinefunction(fn) at the registry lookup level.

    If the registry's add_activity ever wraps coroutine functions in a way that hides their
    async-ness (e.g. functools.wraps with a sync decorator), the dispatcher would route
    them to the thread pool and break I/O concurrency. This test pins that contract.
    """

    async def test_async_activity(ctx: task.ActivityContext, _):
        return None

    registry = worker._Registry()
    name = registry.add_activity(test_async_activity)

    retrieved = registry.get_activity(name)
    assert inspect.iscoroutinefunction(retrieved)
