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


@dataclass
class ActivityExecutionInfo:
    workflow_id: str
    activity_name: str
    task_id: int
    attempt: int | None
    inbound_metadata: dict[str, str]
