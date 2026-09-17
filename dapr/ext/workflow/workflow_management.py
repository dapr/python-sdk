# -*- coding: utf-8 -*-
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

"""Return types for the workflow management APIs.

These back :meth:`DaprWorkflowClient.list_workflow_instances` and
:meth:`DaprWorkflowClient.get_workflow_history`, on both the sync and the async
client.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any, Optional

import dapr.ext.workflow._durabletask.internal.helpers as pbh
import dapr.ext.workflow._durabletask.internal.protos as pb
from dapr.ext.workflow._durabletask.task import FailureDetails


@dataclass(frozen=True)
class WorkflowInstanceIdPage:
    """One page of workflow instance IDs.

    Attributes:
        instance_ids: The instance IDs in this page, which may be empty.
        continuation_token: Token to pass to the next
            :meth:`DaprWorkflowClient.list_workflow_instances` call, or None
            when this is the last page.
    """

    instance_ids: list[str]
    continuation_token: Optional[str]

    @classmethod
    def _from_proto(cls, res: pb.ListInstanceIDsResponse) -> WorkflowInstanceIdPage:
        return cls(
            instance_ids=list(res.instanceIds),
            continuation_token=res.continuationToken if res.HasField('continuationToken') else None,
        )


class WorkflowHistoryEventType(Enum):
    """The kind of a workflow history event.

    Any event type the runtime adds but this SDK version does not know maps to
    :attr:`UNKNOWN` rather than raising, so a newer sidecar never breaks history
    reads.

    Each value is the protobuf field name of the event payload, which is what
    makes that fallback possible. Prefer ``.name`` when displaying or persisting
    a type: ``.value`` is a wire detail and spelled in camelCase.
    """

    UNKNOWN = 'unknown'
    EXECUTION_STARTED = 'executionStarted'
    EXECUTION_COMPLETED = 'executionCompleted'
    EXECUTION_TERMINATED = 'executionTerminated'
    EXECUTION_SUSPENDED = 'executionSuspended'
    EXECUTION_RESUMED = 'executionResumed'
    EXECUTION_STALLED = 'executionStalled'
    TASK_SCHEDULED = 'taskScheduled'
    TASK_COMPLETED = 'taskCompleted'
    TASK_FAILED = 'taskFailed'
    CHILD_WORKFLOW_INSTANCE_CREATED = 'childWorkflowInstanceCreated'
    CHILD_WORKFLOW_INSTANCE_COMPLETED = 'childWorkflowInstanceCompleted'
    CHILD_WORKFLOW_INSTANCE_FAILED = 'childWorkflowInstanceFailed'
    DETACHED_WORKFLOW_INSTANCE_CREATED = 'detachedWorkflowInstanceCreated'
    TIMER_CREATED = 'timerCreated'
    TIMER_FIRED = 'timerFired'
    EVENT_SENT = 'eventSent'
    EVENT_RAISED = 'eventRaised'
    CONTINUE_AS_NEW = 'continueAsNew'
    WORKFLOW_STARTED = 'workflowStarted'
    WORKFLOW_COMPLETED = 'workflowCompleted'

    @classmethod
    def _missing_(cls, value: object) -> WorkflowHistoryEventType:
        return cls.UNKNOWN


# The event types this SDK version knows the runtime can restart from. It is a
# snapshot of a server-side rule, so a sidecar on a different version decides for
# itself; anything it rejects comes back as NOT_FOUND or INVALID_ARGUMENT.
_RERUNNABLE_EVENT_TYPES = frozenset(
    {
        WorkflowHistoryEventType.TASK_SCHEDULED,
        WorkflowHistoryEventType.TIMER_CREATED,
        WorkflowHistoryEventType.CHILD_WORKFLOW_INSTANCE_CREATED,
    }
)


def _failure_details_of(payload: Any) -> Optional[FailureDetails]:
    """Reads the failure off a history event payload, for the types that carry one.

    Every event type has a payload of a different message type, so asking one of
    them for a field only some of the others define is the normal case here, not
    an error. An unset payload reads as no failure.

    Args:
        payload: The event's payload message, or None for an unset event type.

    Returns:
        The failure, or None if this payload has no failure to report.
    """
    try:
        has_failure = payload.HasField('failureDetails')
    except (AttributeError, ValueError):
        return None
    if not has_failure:
        return None

    details = payload.failureDetails
    stack_trace = details.stackTrace
    return FailureDetails(
        details.errorMessage,
        details.errorType,
        stack_trace.value if not pbh.is_empty(stack_trace) else None,
    )


@dataclass(frozen=True)
class WorkflowHistoryEvent:
    """A single event from a workflow instance's execution history.

    The payload of a history event depends on its type, so only the fields that
    apply to :attr:`event_type` are populated; the rest are None. Use
    :attr:`event_id` as the ``event_id`` argument of
    :meth:`DaprWorkflowClient.rerun_workflow_from_event`.

    Attributes:
        event_id: The event's ID within its instance's history. Not a list
            index: rerun matches on this value. The runtime reports -1 for the
            events it assigns no ID to; which types those are is the runtime's
            choice, so treat -1 as "no ID" rather than inferring the type.
        timestamp: When the runtime recorded the event, as a naive UTC
            datetime — the same convention as WorkflowState.created_at.
        event_type: The kind of event.
        name: The name of whatever the event is about, for the event types
            that carry one: the activity, child workflow, external event or
            timer, and the workflow itself on EXECUTION_STARTED.
        task_scheduled_id: For activity and child workflow completion and
            failure events, the event_id of the scheduling event they close out.
            TIMER_FIRED does not carry it; the wire puts that correlation in a
            different field this type does not surface.
        failure_details: The error, for the failure event types and for an
            EXECUTION_COMPLETED that completed a failed workflow.
    """

    event_id: int
    timestamp: datetime
    event_type: WorkflowHistoryEventType
    name: Optional[str]
    task_scheduled_id: Optional[int]
    failure_details: Optional[FailureDetails]

    @property
    def is_rerunnable(self) -> bool:
        """Whether this SDK expects rerun_workflow_from_event to accept this event.

        The runtime has the final say, and a sidecar of a different version may
        disagree. Treat this as a filter, not a guarantee.
        """
        return self.event_type in _RERUNNABLE_EVENT_TYPES

    @classmethod
    def _from_proto(cls, event: pb.HistoryEvent) -> WorkflowHistoryEvent:
        # Which payload is set is itself the event type, and the payload types
        # share field names (`name`, `taskScheduledId`, `failureDetails`) where
        # they share meaning, so read them off the payload rather than
        # enumerating every event type three times over.
        payload_field = event.WhichOneof('eventType')
        payload = getattr(event, payload_field) if payload_field else None

        return cls(
            event_id=event.eventId,
            timestamp=event.timestamp.ToDatetime(),
            event_type=WorkflowHistoryEventType(payload_field),
            name=getattr(payload, 'name', '') or None,
            task_scheduled_id=getattr(payload, 'taskScheduledId', None),
            failure_details=_failure_details_of(payload),
        )
