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

"""Wire-level verification of stateful-history (delta) work-item delivery.

Requires a sidecar whose embedded durabletask-go grpcExecutor implements the feature
(dapr/durabletask-go#110, on dapr master since dapr/dapr#10142). Against an older sidecar
the capability is ignored and every turn arrives as a full send, which is exactly what
``test_delta_delivery_reduces_full_sends`` is written to catch.

Asserting on workflow output alone would prove nothing here: a correct delta path and a
sidecar that never sends deltas produce identical results. The counts come from a gRPC
interceptor watching the real work-item stream.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

import pytest

from tests.integration.workflow_observer import DeliveryCounts, WorkItemObserver

if TYPE_CHECKING:
    from dapr.ext.workflow import WorkflowState

# The released sidecar the default `validate` job installs predates the feature and would
# fail the delta assertions below, so only the dapr-head job runs this module.
pytestmark = pytest.mark.dapr_head

HOST = '127.0.0.1'
GRPC_PORT = '13501'
WORKFLOW_TURNS = 20
COMPLETION_TIMEOUT_S = 60

# The sidecar records how much history a stream holds only *after* rewriting a work item,
# so the first turn (empty past) leaves the watermark at zero and the second still fails
# the "worker holds something" check. Deltas therefore start at the third turn.
MAX_WARMUP_FULL_SENDS = 2


@pytest.fixture(scope='module')
def sidecar(dapr_env):
    return dapr_env.start_sidecar(app_id='test-workflow-stateful-history')


def _run_accumulate(
    sidecar, *, disable_stateful_history: bool
) -> tuple[DeliveryCounts, WorkflowState]:
    """Runs the chain on a fresh runtime and returns its delivery counts and final state.

    A new runtime per run means a new work-item stream, so the sidecar's warm set starts
    empty and the counts describe this run alone. The workflow and activity are defined
    per run because ``register_workflow`` stamps the function object, so the same callable
    cannot be registered against a second runtime.
    """
    from dapr.ext.workflow import (
        DaprWorkflowContext,
        WorkflowActivityContext,
        WorkflowRuntime,
    )
    from dapr.ext.workflow.dapr_workflow_client import DaprWorkflowClient

    def plus_one(ctx: WorkflowActivityContext, value: int) -> int:
        return value + 1

    def accumulate(ctx: DaprWorkflowContext, start: int):
        """A long sequential chain, so each activity result is its own turn.

        The committed history grows on every turn, which is what makes the omitted
        prefix (and therefore the delta) large enough to be worth measuring.
        """
        current = start
        for _ in range(WORKFLOW_TURNS):
            current = yield ctx.call_activity(plus_one, input=current)
        return current

    observer = WorkItemObserver()
    runtime = WorkflowRuntime(
        host=HOST,
        port=GRPC_PORT,
        interceptors=[observer],
        disable_stateful_history=disable_stateful_history,
    )
    runtime.register_workflow(accumulate)
    runtime.register_activity(plus_one)
    runtime.start()
    try:
        workflow_client = DaprWorkflowClient(host=HOST, port=GRPC_PORT)
        instance_id = workflow_client.schedule_new_workflow(accumulate, input=0)
        state = workflow_client.wait_for_workflow_completion(
            instance_id, timeout_in_seconds=COMPLETION_TIMEOUT_S
        )
    finally:
        runtime.shutdown()

    assert state is not None, 'workflow did not reach a terminal state'
    return observer.counts_for(instance_id), state


def _assert_completed(state: WorkflowState) -> None:
    from dapr.ext.workflow import WorkflowStatus

    assert state.runtime_status == WorkflowStatus.COMPLETED
    assert state.serialized_output == json.dumps(WORKFLOW_TURNS)


def test_delta_delivery_reduces_full_sends(sidecar):
    """Most turns must arrive as deltas, with only the unavoidable warm-up full sends."""
    counts, state = _run_accumulate(sidecar, disable_stateful_history=False)

    _assert_completed(state)
    assert counts.deltas > 0, f'sidecar never sent a delta: {counts}'
    assert counts.full_sends <= MAX_WARMUP_FULL_SENDS, f'too many full sends: {counts}'
    assert counts.deltas >= WORKFLOW_TURNS - MAX_WARMUP_FULL_SENDS, (
        f'expected a delta for nearly every turn: {counts}'
    )


def test_warm_stream_never_misses_its_cache(sidecar):
    """A steady stream should reconstruct every delta locally, never refetching history."""
    counts, state = _run_accumulate(sidecar, disable_stateful_history=False)

    _assert_completed(state)
    assert counts.history_fetches == 0, f'unexpected GetInstanceHistory recovery: {counts}'


def test_disabled_receives_only_full_histories(sidecar):
    """With the capability withheld, the sidecar must fall back to full sends throughout."""
    counts, state = _run_accumulate(sidecar, disable_stateful_history=True)

    _assert_completed(state)
    assert counts.deltas == 0, f'delta sent to a worker that never advertised support: {counts}'
    assert counts.full_sends >= WORKFLOW_TURNS, f'expected a full send per turn: {counts}'
