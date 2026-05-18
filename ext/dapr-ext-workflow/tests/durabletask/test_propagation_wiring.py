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

"""Tests for runtime-side history propagation wiring:

- :meth:`OrchestrationContext.call_activity(propagation=...)` and
  :meth:`call_sub_orchestrator(propagation=...)` set ``historyPropagationScope``
  on the emitted action.
- :meth:`OrchestrationContext.get_propagated_history` returns the history that
  the worker parsed off the incoming ``WorkflowRequest``.
- :meth:`ActivityContext.get_propagated_history` returns the history that the
  worker parsed off the incoming ``ActivityRequest``.
"""

from __future__ import annotations

import json
import logging

import dapr.ext.workflow._durabletask.internal.helpers as helpers
import dapr.ext.workflow._durabletask.internal.protos as pb
from dapr.ext.workflow import PropagatedHistory, PropagationScope
from dapr.ext.workflow._durabletask import task, worker

TEST_LOGGER = logging.getLogger('tests')
TEST_INSTANCE_ID = 'wiring-instance'


# --- Helpers -----------------------------------------------------------------


def _no_op_activity(_ctx, _inp):
    return None


def _single_chunk_history(workflow_name: str = 'Parent') -> pb.PropagatedHistory:
    """Build a tiny but valid PropagatedHistory proto."""
    start = pb.HistoryEvent(
        eventId=0, executionStarted=pb.ExecutionStartedEvent(name=workflow_name)
    )
    return pb.PropagatedHistory(
        scope=pb.HISTORY_PROPAGATION_SCOPE_OWN_HISTORY,
        chunks=[
            pb.PropagatedHistoryChunk(
                appId='parent-app',
                instanceId='parent-instance',
                workflowName=workflow_name,
                rawEvents=[start.SerializeToString()],
            ),
        ],
    )


# --- Outgoing: actions carry historyPropagationScope ------------------------


def test_call_activity_emits_no_propagation_by_default():
    def orchestrator(ctx: task.OrchestrationContext, _):
        yield ctx.call_activity(_no_op_activity, input=1)

    registry = worker._Registry()
    name = registry.add_orchestrator(orchestrator)
    executor = worker._OrchestrationExecutor(registry, TEST_LOGGER)
    result = executor.execute(
        TEST_INSTANCE_ID,
        [],
        [
            helpers.new_workflow_started_event(),
            helpers.new_execution_started_event(name, TEST_INSTANCE_ID, encoded_input=None),
        ],
    )

    assert len(result.actions) == 1
    schedule = result.actions[0].scheduleTask
    assert not schedule.HasField('historyPropagationScope')


def test_call_activity_emits_own_history_when_requested():
    def orchestrator(ctx: task.OrchestrationContext, _):
        yield ctx.call_activity(_no_op_activity, input=1, propagation=PropagationScope.OWN_HISTORY)

    registry = worker._Registry()
    name = registry.add_orchestrator(orchestrator)
    executor = worker._OrchestrationExecutor(registry, TEST_LOGGER)
    result = executor.execute(
        TEST_INSTANCE_ID,
        [],
        [
            helpers.new_workflow_started_event(),
            helpers.new_execution_started_event(name, TEST_INSTANCE_ID, encoded_input=None),
        ],
    )

    schedule = result.actions[0].scheduleTask
    assert schedule.HasField('historyPropagationScope')
    assert schedule.historyPropagationScope == pb.HISTORY_PROPAGATION_SCOPE_OWN_HISTORY


def test_call_sub_orchestrator_emits_lineage_when_requested():
    def orchestrator(ctx: task.OrchestrationContext, _):
        yield ctx.call_sub_orchestrator('ChildWf', input=None, propagation=PropagationScope.LINEAGE)

    registry = worker._Registry()
    name = registry.add_orchestrator(orchestrator)
    executor = worker._OrchestrationExecutor(registry, TEST_LOGGER)
    result = executor.execute(
        TEST_INSTANCE_ID,
        [],
        [
            helpers.new_workflow_started_event(),
            helpers.new_execution_started_event(name, TEST_INSTANCE_ID, encoded_input=None),
        ],
    )

    create = result.actions[0].createChildWorkflow
    assert create.HasField('historyPropagationScope')
    assert create.historyPropagationScope == pb.HISTORY_PROPAGATION_SCOPE_LINEAGE


# --- Incoming: ctx.get_propagated_history is populated ----------------------


def test_orchestration_executor_exposes_propagated_history():
    """Build an executor, run an orchestrator that reads
    ctx.get_propagated_history, and verify the propagated chunk reached it."""

    captured: dict[str, PropagatedHistory | None] = {'history': None}

    def orchestrator(ctx: task.OrchestrationContext, _):
        captured['history'] = ctx.get_propagated_history()
        return 'done'

    registry = worker._Registry()
    name = registry.add_orchestrator(orchestrator)
    executor = worker._OrchestrationExecutor(registry, TEST_LOGGER)

    propagated = PropagatedHistory.from_proto(_single_chunk_history())
    assert propagated is not None

    executor.execute(
        TEST_INSTANCE_ID,
        [],
        [
            helpers.new_workflow_started_event(),
            helpers.new_execution_started_event(name, TEST_INSTANCE_ID, encoded_input=None),
        ],
        propagated_history=propagated,
    )

    history = captured['history']
    assert history is not None
    assert history.get_app_ids() == ['parent-app']
    assert history.get_workflow_by_name('Parent').instance_id == 'parent-instance'


def test_orchestration_executor_propagated_history_is_none_by_default():
    captured: dict[str, PropagatedHistory | None] = {'history': 'sentinel'}  # type: ignore[dict-item]

    def orchestrator(ctx: task.OrchestrationContext, _):
        captured['history'] = ctx.get_propagated_history()
        return 'done'

    registry = worker._Registry()
    name = registry.add_orchestrator(orchestrator)
    executor = worker._OrchestrationExecutor(registry, TEST_LOGGER)
    executor.execute(
        TEST_INSTANCE_ID,
        [],
        [
            helpers.new_workflow_started_event(),
            helpers.new_execution_started_event(name, TEST_INSTANCE_ID, encoded_input=None),
        ],
    )
    assert captured['history'] is None


def test_activity_executor_exposes_propagated_history():
    captured: dict[str, PropagatedHistory | None] = {'history': None}

    def reading_activity(ctx: task.ActivityContext, _):
        captured['history'] = ctx.get_propagated_history()
        return 'ok'

    registry = worker._Registry()
    activity_name = registry.add_activity(reading_activity)
    executor = worker._ActivityExecutor(registry, TEST_LOGGER)

    propagated = PropagatedHistory.from_proto(_single_chunk_history('Caller'))
    assert propagated is not None

    encoded_output = executor.execute(
        orchestration_id='wf-1',
        name=activity_name,
        task_id=1,
        encoded_input=json.dumps(None),
        task_execution_id='exec-1',
        propagated_history=propagated,
    )
    assert encoded_output == '"ok"'

    history = captured['history']
    assert history is not None
    assert history.get_app_ids() == ['parent-app']
    assert history.get_workflow_by_name('Caller').instance_id == 'parent-instance'


def test_activity_executor_propagated_history_is_none_by_default():
    captured: dict[str, PropagatedHistory | None] = {'history': 'sentinel'}  # type: ignore[dict-item]

    def reading_activity(ctx: task.ActivityContext, _):
        captured['history'] = ctx.get_propagated_history()
        return None

    registry = worker._Registry()
    activity_name = registry.add_activity(reading_activity)
    executor = worker._ActivityExecutor(registry, TEST_LOGGER)
    executor.execute(
        orchestration_id='wf-1',
        name=activity_name,
        task_id=1,
        encoded_input=json.dumps(None),
        task_execution_id='exec-1',
    )
    assert captured['history'] is None
