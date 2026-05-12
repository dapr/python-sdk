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

"""Unit tests for the PropagatedHistory query API.

Ported from the Go reference implementation at
durabletask-go/api/propagation_test.go.
"""

from __future__ import annotations

import dapr.ext.workflow._durabletask.internal.protos as pb
import pytest
from dapr.ext.workflow import (
    PropagatedHistory,
    PropagationNotFoundError,
    PropagationScope,
)
from google.protobuf import wrappers_pb2

# --- Test history fixtures ---------------------------------------------------

# The fixtures below mirror Go's makeTestHistory. Two chunks:
#   appA / wf-001 "MerchantCheckout":
#     [0] ExecutionStarted MerchantCheckout
#     [1] TaskScheduled ValidateMerchant (eventId=1)
#     [-1] TaskCompleted taskScheduledId=1
#     [2] ChildWorkflowInstanceCreated ProcessPayment (instance=wf-002)
#
#   appB / wf-002 "ProcessPayment":
#     [0] ExecutionStarted ProcessPayment
#     [1] TaskScheduled ValidateCard (eventId=1, exec-2) — completed
#     [-1] TaskCompleted taskScheduledId=1
#     [2] TaskScheduled ValidateCard (eventId=2, exec-3) — failed
#     [-1] TaskFailed taskScheduledId=2
#     [3] ChildWorkflowInstanceCreated FraudDetection (instance=wf-003)


def _str_value(s: str) -> wrappers_pb2.StringValue:
    return wrappers_pb2.StringValue(value=s)


def _execution_started(name: str) -> pb.HistoryEvent:
    return pb.HistoryEvent(
        eventId=0,
        executionStarted=pb.ExecutionStartedEvent(name=name),
    )


def _task_scheduled(event_id: int, name: str, exec_id: str, raw_input: str) -> pb.HistoryEvent:
    return pb.HistoryEvent(
        eventId=event_id,
        taskScheduled=pb.TaskScheduledEvent(
            name=name,
            taskExecutionId=exec_id,
            input=_str_value(raw_input),
        ),
    )


def _task_completed(task_scheduled_id: int, exec_id: str, result: str) -> pb.HistoryEvent:
    return pb.HistoryEvent(
        eventId=-1,
        taskCompleted=pb.TaskCompletedEvent(
            taskScheduledId=task_scheduled_id,
            taskExecutionId=exec_id,
            result=_str_value(result),
        ),
    )


def _task_failed(task_scheduled_id: int, exec_id: str, message: str) -> pb.HistoryEvent:
    return pb.HistoryEvent(
        eventId=-1,
        taskFailed=pb.TaskFailedEvent(
            taskScheduledId=task_scheduled_id,
            taskExecutionId=exec_id,
            failureDetails=pb.TaskFailureDetails(errorMessage=message),
        ),
    )


def _child_wf_created(event_id: int, name: str, instance_id: str) -> pb.HistoryEvent:
    return pb.HistoryEvent(
        eventId=event_id,
        childWorkflowInstanceCreated=pb.ChildWorkflowInstanceCreatedEvent(
            name=name,
            instanceId=instance_id,
        ),
    )


def _make_chunk(
    app_id: str,
    instance_id: str,
    workflow_name: str,
    events: list[pb.HistoryEvent],
) -> pb.PropagatedHistoryChunk:
    return pb.PropagatedHistoryChunk(
        appId=app_id,
        instanceId=instance_id,
        workflowName=workflow_name,
        rawEvents=[e.SerializeToString() for e in events],
    )


def _make_proto_history() -> pb.PropagatedHistory:
    chunk_a_events = [
        _execution_started('MerchantCheckout'),
        _task_scheduled(1, 'ValidateMerchant', 'exec-1', '{"merchant":"abc"}'),
        _task_completed(1, 'exec-1', 'true'),
        _child_wf_created(2, 'ProcessPayment', 'wf-002'),
    ]
    chunk_b_events = [
        _execution_started('ProcessPayment'),
        _task_scheduled(1, 'ValidateCard', 'exec-2', '{"card":"4242"}'),
        _task_completed(1, 'exec-2', 'true'),
        _task_scheduled(2, 'ValidateCard', 'exec-3', '{"card":"4242","retry":true}'),
        _task_failed(2, 'exec-3', 'card declined'),
        _child_wf_created(3, 'FraudDetection', 'wf-003'),
    ]
    return pb.PropagatedHistory(
        scope=pb.HISTORY_PROPAGATION_SCOPE_LINEAGE,
        chunks=[
            _make_chunk('appA', 'wf-001', 'MerchantCheckout', chunk_a_events),
            _make_chunk('appB', 'wf-002', 'ProcessPayment', chunk_b_events),
        ],
    )


@pytest.fixture
def history() -> PropagatedHistory:
    parsed = PropagatedHistory.from_proto(_make_proto_history())
    assert parsed is not None
    return parsed


# --- Top-level structural queries -------------------------------------------


def test_scope_is_preserved(history: PropagatedHistory):
    assert history.scope == PropagationScope.LINEAGE


def test_events_are_flattened_in_chunk_order(history: PropagatedHistory):
    assert len(history.events) == 10
    assert history.events[0].executionStarted.name == 'MerchantCheckout'
    assert history.events[4].executionStarted.name == 'ProcessPayment'


def test_get_app_ids_returns_unique_ordered(history: PropagatedHistory):
    assert history.get_app_ids() == ['appA', 'appB']


def test_get_events_by_app_id(history: PropagatedHistory):
    appa_events = history.get_events_by_app_id('appA')
    appb_events = history.get_events_by_app_id('appB')
    assert len(appa_events) == 4
    assert len(appb_events) == 6
    assert history.get_events_by_app_id('missing') == []


def test_get_events_by_instance_id(history: PropagatedHistory):
    wf001_events = history.get_events_by_instance_id('wf-001')
    assert len(wf001_events) == 4
    assert wf001_events[0].executionStarted.name == 'MerchantCheckout'


def test_get_events_by_workflow_name(history: PropagatedHistory):
    pp_events = history.get_events_by_workflow_name('ProcessPayment')
    assert len(pp_events) == 6
    assert pp_events[0].executionStarted.name == 'ProcessPayment'


# --- Workflow-level queries --------------------------------------------------


def test_get_workflows_returns_chunks_in_order(history: PropagatedHistory):
    workflows = history.get_workflows()
    assert len(workflows) == 2

    assert workflows[0].name == 'MerchantCheckout'
    assert workflows[0].app_id == 'appA'
    assert workflows[0].instance_id == 'wf-001'

    assert workflows[1].name == 'ProcessPayment'
    assert workflows[1].app_id == 'appB'
    assert workflows[1].instance_id == 'wf-002'


def test_get_workflow_by_name_returns_match(history: PropagatedHistory):
    wf = history.get_workflow_by_name('ProcessPayment')
    assert wf.name == 'ProcessPayment'
    assert wf.instance_id == 'wf-002'


def test_get_workflow_by_name_raises_when_missing(history: PropagatedHistory):
    with pytest.raises(PropagationNotFoundError):
        history.get_workflow_by_name('NotARealWorkflow')


def test_get_workflows_by_name_returns_all_matches():
    """If the same workflow name appears in multiple chunks (e.g. ContinueAsNew
    or recursion), get_workflows_by_name returns every occurrence and
    get_workflow_by_name returns the last."""

    chunk_events = [_execution_started('Loop')]
    proto = pb.PropagatedHistory(
        scope=pb.HISTORY_PROPAGATION_SCOPE_LINEAGE,
        chunks=[
            _make_chunk('appA', 'wf-1', 'Loop', chunk_events),
            _make_chunk('appA', 'wf-2', 'Loop', chunk_events),
        ],
    )
    ph = PropagatedHistory.from_proto(proto)
    assert ph is not None

    all_loops = ph.get_workflows_by_name('Loop')
    assert len(all_loops) == 2
    assert ph.get_workflow_by_name('Loop').instance_id == 'wf-2'


# --- Activity resolution ----------------------------------------------------


def test_get_activity_by_name_returns_completed_result(history: PropagatedHistory):
    merchant = history.get_workflow_by_name('MerchantCheckout')
    activity = merchant.get_activity_by_name('ValidateMerchant')

    assert activity.name == 'ValidateMerchant'
    assert activity.started
    assert activity.completed
    assert not activity.failed
    assert activity.input == '{"merchant":"abc"}'
    assert activity.output == 'true'
    assert activity.error is None


def test_get_activities_by_name_returns_all_invocations(history: PropagatedHistory):
    payment = history.get_workflow_by_name('ProcessPayment')
    cards = payment.get_activities_by_name('ValidateCard')

    assert len(cards) == 2
    assert cards[0].completed and not cards[0].failed
    assert cards[0].output == 'true'

    assert cards[1].failed and not cards[1].completed
    assert cards[1].error is not None
    assert cards[1].error.errorMessage == 'card declined'


def test_get_activity_by_name_returns_last_invocation(history: PropagatedHistory):
    """get_activity_by_name returns the most recent invocation in execution
    order, matching Go semantics."""
    payment = history.get_workflow_by_name('ProcessPayment')
    last = payment.get_activity_by_name('ValidateCard')
    assert last.failed
    assert last.error is not None
    assert last.error.errorMessage == 'card declined'


def test_get_activity_by_name_raises_when_missing(history: PropagatedHistory):
    payment = history.get_workflow_by_name('ProcessPayment')
    with pytest.raises(PropagationNotFoundError):
        payment.get_activity_by_name('NotAnActivity')


def test_activity_not_yet_completed_reports_started_only():
    """A TaskScheduled with no matching TaskCompleted/TaskFailed is reported as
    started but neither completed nor failed."""
    events = [
        _execution_started('StillRunning'),
        _task_scheduled(1, 'Pending', 'exec-1', 'in'),
    ]
    proto = pb.PropagatedHistory(
        scope=pb.HISTORY_PROPAGATION_SCOPE_OWN_HISTORY,
        chunks=[_make_chunk('appA', 'wf-1', 'StillRunning', events)],
    )
    ph = PropagatedHistory.from_proto(proto)
    assert ph is not None
    pending = ph.get_workflow_by_name('StillRunning').get_activity_by_name('Pending')

    assert pending.started
    assert not pending.completed
    assert not pending.failed
    assert pending.input == 'in'
    assert pending.output is None


# --- Child workflow resolution ----------------------------------------------


def test_get_child_workflow_by_name(history: PropagatedHistory):
    merchant = history.get_workflow_by_name('MerchantCheckout')
    child = merchant.get_child_workflow_by_name('ProcessPayment')

    assert child.name == 'ProcessPayment'
    assert child.started


def test_get_child_workflow_by_name_raises_when_missing(history: PropagatedHistory):
    merchant = history.get_workflow_by_name('MerchantCheckout')
    with pytest.raises(PropagationNotFoundError):
        merchant.get_child_workflow_by_name('NotAChild')


# --- from_proto / structural validation -------------------------------------


def test_from_proto_returns_none_for_none_input():
    assert PropagatedHistory.from_proto(None) is None


def test_from_proto_rejects_chunk_with_empty_app_id():
    bad_proto = pb.PropagatedHistory(
        scope=pb.HISTORY_PROPAGATION_SCOPE_LINEAGE,
        chunks=[
            pb.PropagatedHistoryChunk(
                appId='',
                instanceId='wf-1',
                workflowName='X',
                rawEvents=[],
            ),
        ],
    )
    with pytest.raises(ValueError, match='empty appId'):
        PropagatedHistory.from_proto(bad_proto)


def test_from_proto_rejects_malformed_raw_event():
    bad_proto = pb.PropagatedHistory(
        scope=pb.HISTORY_PROPAGATION_SCOPE_LINEAGE,
        chunks=[
            pb.PropagatedHistoryChunk(
                appId='appA',
                instanceId='wf-1',
                workflowName='X',
                rawEvents=[b'\xff\xff\xff\xff\xff\xff\xff\xff garbage'],
            ),
        ],
    )
    with pytest.raises(ValueError, match='rawEvent'):
        PropagatedHistory.from_proto(bad_proto)


def test_from_proto_round_trip_preserves_events():
    proto = _make_proto_history()
    ph = PropagatedHistory.from_proto(proto)
    assert ph is not None
    assert len(ph.events) == 10
    assert ph.scope == PropagationScope.LINEAGE
    assert ph.get_app_ids() == ['appA', 'appB']


def test_from_proto_handles_empty_chunks():
    proto = pb.PropagatedHistory(
        scope=pb.HISTORY_PROPAGATION_SCOPE_NONE,
        chunks=[],
    )
    ph = PropagatedHistory.from_proto(proto)
    assert ph is not None
    assert ph.events == []
    assert ph.get_app_ids() == []
    assert ph.get_workflows() == []
