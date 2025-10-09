"""
Copyright 2025 The Dapr Authors
Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at
    http://www.apache.org/licenses/LICENSE-2.0
Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
"""

from __future__ import annotations

from datetime import datetime, timezone

from dapr.ext.workflow.aio import AsyncWorkflowContext
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


def test_workflow_execution_info_minimal():
    ei = WorkflowExecutionInfo(inbound_metadata={'k': 'v'})
    assert ei.inbound_metadata == {'k': 'v'}


def test_activity_execution_info_minimal():
    aei = ActivityExecutionInfo(inbound_metadata={'m': 'v'})
    assert aei.inbound_metadata == {'m': 'v'}


def test_workflow_activity_context_execution_info_trace_fields():
    base = _FakeActivityCtx()
    actx = WorkflowActivityContext(base)
    aei = ActivityExecutionInfo(inbound_metadata={})
    actx._set_execution_info(aei)
    got = actx.execution_info
    assert got is not None
    assert got.inbound_metadata == {}
