from __future__ import annotations

from dataclasses import dataclass


@dataclass
class WorkflowExecutionInfo:
    workflow_id: str
    workflow_name: str
    is_replaying: bool
    history_event_sequence: int | None
    inbound_metadata: dict[str, str]
    parent_instance_id: str | None
    # Tracing (engine-provided)
    trace_parent: str | None = None
    trace_state: str | None = None
    workflow_span_id: str | None = None


@dataclass
class ActivityExecutionInfo:
    workflow_id: str
    activity_name: str
    task_id: int
    attempt: int | None
    inbound_metadata: dict[str, str]
    # Tracing (engine-provided)
    trace_parent: str | None = None
    trace_state: str | None = None
