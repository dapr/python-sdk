from __future__ import annotations

from datetime import datetime, timezone

from dapr.ext.workflow.async_context import AsyncWorkflowContext
from dapr.ext.workflow.dapr_workflow_context import DaprWorkflowContext
from dapr.ext.workflow.execution_info import ActivityExecutionInfo, WorkflowExecutionInfo
from dapr.ext.workflow.workflow_activity_context import WorkflowActivityContext


class _FakeOrchCtx:
    def __init__(self):
        self.instance_id = 'wf-123'
        self.current_utc_datetime = datetime(2025, 1, 1, tzinfo=timezone.utc)
        self.is_replaying = False
        self.workflow_name = 'wf_name'
        self.parent_instance_id = 'parent-1'
        self.history_event_sequence = 42
        self.trace_parent = '00-aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa-bbbbbbbbbbbbbbbb-01'
        self.trace_state = 'vendor=state'
        self.orchestration_span_id = 'bbbbbbbbbbbbbbbb'


class _FakeActivityCtx:
    def __init__(self):
        self.orchestration_id = 'wf-123'
        self.task_id = 7
        self.trace_parent = '00-cccccccccccccccccccccccccccccccc-dddddddddddddddd-01'
        self.trace_state = 'v=1'


def test_dapr_workflow_context_trace_properties():
    base = _FakeOrchCtx()
    ctx = DaprWorkflowContext(base)

    assert ctx.trace_parent == base.trace_parent
    assert ctx.trace_state == base.trace_state
    # SDK renames orchestration span id to workflow_span_id
    assert ctx.workflow_span_id == base.orchestration_span_id


def test_async_workflow_context_trace_properties():
    base = _FakeOrchCtx()
    actx = AsyncWorkflowContext(DaprWorkflowContext(base))

    assert actx.trace_parent == base.trace_parent
    assert actx.trace_state == base.trace_state
    assert actx.workflow_span_id == base.orchestration_span_id


def test_workflow_execution_info_trace_fields():
    ei = WorkflowExecutionInfo(
        workflow_id='wf-123',
        workflow_name='wf_name',
        is_replaying=False,
        history_event_sequence=1,
        inbound_metadata={'k': 'v'},
        parent_instance_id='parent-1',
        trace_parent='00-aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa-bbbbbbbbbbbbbbbb-01',
        trace_state='vendor=state',
        workflow_span_id='bbbbbbbbbbbbbbbb',
    )
    assert ei.trace_parent and ei.trace_state and ei.workflow_span_id


def test_activity_execution_info_trace_fields():
    aei = ActivityExecutionInfo(
        workflow_id='wf-123',
        activity_name='act',
        task_id=7,
        attempt=1,
        inbound_metadata={'m': 'v'},
        trace_parent='00-cccccccccccccccccccccccccccccccc-dddddddddddddddd-01',
        trace_state='v=1',
    )
    assert aei.trace_parent and aei.trace_state


def test_workflow_activity_context_execution_info_trace_fields():
    base = _FakeActivityCtx()
    actx = WorkflowActivityContext(base)
    aei = ActivityExecutionInfo(
        workflow_id=base.orchestration_id,
        activity_name='noop',
        task_id=base.task_id,
        attempt=1,
        inbound_metadata={},
        trace_parent=base.trace_parent,
        trace_state=base.trace_state,
    )
    actx._set_execution_info(aei)
    got = actx.execution_info
    assert got is not None
    assert got.trace_parent == base.trace_parent
    assert got.trace_state == base.trace_state
