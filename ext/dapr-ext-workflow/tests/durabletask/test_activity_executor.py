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

import json
import logging
from typing import Any, Optional, Tuple

from dapr.ext.workflow._durabletask import task, worker

logging.basicConfig(
    format='%(asctime)s.%(msecs)03d %(name)s %(levelname)s: %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
    level=logging.DEBUG,
)
TEST_LOGGER = logging.getLogger('tests')
TEST_INSTANCE_ID = 'abc123'
TEST_TASK_ID = 42


def test_activity_inputs():
    """Validates activity function input population"""

    def test_activity(ctx: task.ActivityContext, test_input: Any):
        # return all activity inputs back as the output
        return test_input, ctx.orchestration_id, ctx.task_id

    activity_input = 'Hello, 世界!'
    executor, name = _get_activity_executor(test_activity)
    result = executor.execute(
        test_activity, TEST_INSTANCE_ID, name, TEST_TASK_ID, json.dumps(activity_input)
    )
    assert result is not None

    result_input, result_orchestration_id, result_task_id = json.loads(result)
    assert activity_input == result_input
    assert TEST_INSTANCE_ID == result_orchestration_id
    assert TEST_TASK_ID == result_task_id


def test_activity_not_registered():
    """Dispatch site passes ``fn=None`` for unknown activity names. Executor surfaces
    that as ``ActivityNotRegisteredError`` carrying the requested name.
    """
    executor = worker._ActivityExecutor(TEST_LOGGER)

    caught_exception: Optional[Exception] = None
    try:
        executor.execute(None, TEST_INSTANCE_ID, 'Bogus', TEST_TASK_ID, None)
    except Exception as ex:
        caught_exception = ex

    assert type(caught_exception) is worker.ActivityNotRegisteredError
    assert 'Bogus' in str(caught_exception)


def test_sync_execute_rejects_async_activity():
    """Sync ``execute`` must raise a clear RuntimeError when the activity returns a
    coroutine. Guards against ``_is_async_callable`` missing an async callable at
    registration; without this, JSON encoding would fail with a confusing TypeError.
    """

    async def async_activity(ctx: task.ActivityContext, _):
        return 'never reached'

    executor, name = _get_activity_executor(async_activity)

    caught_exception: Optional[Exception] = None
    try:
        executor.execute(async_activity, TEST_INSTANCE_ID, name, TEST_TASK_ID, None)
    except Exception as ex:
        caught_exception = ex

    assert type(caught_exception) is RuntimeError
    assert 'returned a coroutine' in str(caught_exception)


def _get_activity_executor(fn: task.Activity) -> Tuple[worker._ActivityExecutor, str]:
    registry = worker._Registry()
    name = registry.add_activity(fn)
    executor = worker._ActivityExecutor(TEST_LOGGER)
    return executor, name
