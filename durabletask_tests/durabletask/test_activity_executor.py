# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

import json
import logging
from typing import Any, Optional, Tuple

from durabletask import task, worker

logging.basicConfig(
    format="%(asctime)s.%(msecs)03d %(name)s %(levelname)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    level=logging.DEBUG,
)
TEST_LOGGER = logging.getLogger("tests")
TEST_INSTANCE_ID = "abc123"
TEST_TASK_ID = 42


def test_activity_inputs():
    """Validates activity function input population"""

    def test_activity(ctx: task.ActivityContext, test_input: Any):
        # return all activity inputs back as the output
        return test_input, ctx.orchestration_id, ctx.task_id

    activity_input = "Hello, 世界!"
    executor, name = _get_activity_executor(test_activity)
    result = executor.execute(TEST_INSTANCE_ID, name, TEST_TASK_ID, json.dumps(activity_input))
    assert result is not None

    result_input, result_orchestration_id, result_task_id = json.loads(result)
    assert activity_input == result_input
    assert TEST_INSTANCE_ID == result_orchestration_id
    assert TEST_TASK_ID == result_task_id


def test_activity_not_registered():
    def test_activity(ctx: task.ActivityContext, _):
        pass  # not used

    executor, _ = _get_activity_executor(test_activity)

    caught_exception: Optional[Exception] = None
    try:
        executor.execute(TEST_INSTANCE_ID, "Bogus", TEST_TASK_ID, None)
    except Exception as ex:
        caught_exception = ex

    assert type(caught_exception) is worker.ActivityNotRegisteredError
    assert "Bogus" in str(caught_exception)


def _get_activity_executor(fn: task.Activity) -> Tuple[worker._ActivityExecutor, str]:
    registry = worker._Registry()
    name = registry.add_activity(fn)
    executor = worker._ActivityExecutor(registry, TEST_LOGGER)
    return executor, name
