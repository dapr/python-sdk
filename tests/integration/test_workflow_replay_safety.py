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

"""End-to-end verification of replay-safe workflow context behavior.

These tests run workflows through a real Dapr sidecar. After an activity                                
completes, the workflow is resumed by replaying its history, so the replay                              
assertions exercise ``DaprWorkflowContext`` rather than only the underlying                             
deterministic context.
"""

from __future__ import annotations

import json
from typing import Any
from uuid import UUID

import pytest

pytestmark = pytest.mark.dapr_head

HOST = '127.0.0.1'
GRPC_PORT = '13501'
COMPLETION_TIMEOUT_S = 60
GUID_COUNT = 3


@pytest.fixture(scope='module')
def sidecar(dapr_env):
    """Start the Dapr sidecar used by the workflow replay tests."""
    return dapr_env.start_sidecar(app_id='test-workflow-replay-safety')


def _run_workflow(
    sidecar, workflow, *, activities: tuple[Any, ...] = ()
) -> dict[str, Any] | list[str]:
    """Run a workflow to completion through a real Dapr sidecar and decode its JSON output."""
    from dapr.ext.workflow import DaprWorkflowClient, WorkflowRuntime

    runtime = WorkflowRuntime(host=HOST, port=GRPC_PORT)
    runtime.register_workflow(workflow)
    for activity in activities:
        runtime.register_activity(activity)

    client = DaprWorkflowClient(host=HOST, port=GRPC_PORT)
    runtime.start()
    try:
        instance_id = client.schedule_new_workflow(workflow)
        state = client.wait_for_workflow_completion(
            instance_id, timeout_in_seconds=COMPLETION_TIMEOUT_S
        )
    finally:
        client.close()
        runtime.shutdown()

    assert state is not None, 'workflow did not reach a terminal state'
    assert state.runtime_status.name == 'COMPLETED'
    return json.loads(state.serialized_output)


def test_new_guid_generates_unique_guids_within_execution(sidecar):
    """Each call to ``new_guid()`` produces a unique GUID within one execution."""
    from dapr.ext.workflow import DaprWorkflowContext, WorkflowActivityContext

    def echo_guids(ctx: WorkflowActivityContext, values: list[str]) -> list[str]:
        return values

    def generate_guids(ctx: DaprWorkflowContext, _input: None):
        generated_guids = [str(ctx.new_guid()) for _ in range(GUID_COUNT)]
        yield ctx.call_activity(echo_guids, input=generated_guids)
        return generated_guids

    generated_guids = _run_workflow(sidecar, generate_guids, activities=(echo_guids,))

    assert isinstance(generated_guids, list)

    # Validate serialized GUIDs
    for value in generated_guids:
        UUID(value)

    assert len(set(generated_guids)) == len(generated_guids)


def test_new_guid_is_deterministic_across_replays(sidecar):
    """GUID sequences remain unchanged when the workflow replays its history.

    The echo activity returns the GUIDS from the initial execution.
    During replay, that result comes from history instead of re-running the
    activity, so comparing the generated and echoed values detects if replay
    produced different GUIDs than the original execution.
    """
    from dapr.ext.workflow import DaprWorkflowContext, WorkflowActivityContext

    def echo_guids(ctx: WorkflowActivityContext, values: list[str]) -> list[str]:
        return values

    def generate_guids(ctx: DaprWorkflowContext, _input: None):
        first_guids = [str(ctx.new_guid()) for _ in range(GUID_COUNT)]
        first_echo = yield ctx.call_activity(echo_guids, input=first_guids)

        second_guids = [str(ctx.new_guid()) for _ in range(GUID_COUNT)]
        second_echo = yield ctx.call_activity(echo_guids, input=second_guids)

        return {
            'first_guids': first_guids,
            'first_echo': first_echo,
            'second_guids': second_guids,
            'second_echo': second_echo,
        }

    result = _run_workflow(sidecar, generate_guids, activities=(echo_guids,))

    assert isinstance(result, dict)
    assert result['first_guids'] == result['first_echo']
    assert result['second_guids'] == result['second_echo']

    # Validate serialized GUIDs
    for values in (result['first_guids'], result['second_guids']):
        for value in values:
            UUID(value)

    all_guids = result['first_guids'] + result['second_guids']                                              
    assert len(set(all_guids)) == len(all_guids)
