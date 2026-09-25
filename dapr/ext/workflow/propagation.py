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

"""Workflow history propagation types.

Public surface for the propagation feature: the :class:`PropagationScope`
enum used when scheduling activities or child workflows, plus the
:class:`PropagatedHistory` query API exposed on the receiving side via
:meth:`WorkflowContext.get_propagated_history` and
:meth:`WorkflowActivityContext.get_propagated_history`.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

import dapr.ext.workflow._durabletask.internal.helpers as pbh
import dapr.ext.workflow._durabletask.internal.protos as pb


class PropagationScope(Enum):
    """Controls how a parent workflow's history is propagated to children.

    Values map 1:1 to the protobuf ``HistoryPropagationScope`` enum; the
    plumbing layer reads ``.value`` when writing to proto fields.

    * ``OWN_HISTORY`` — propagate the caller's events only; drop any ancestor
      chain. Use as a trust boundary, where downstream code should only see
      the immediate caller.
    * ``LINEAGE`` — propagate the caller's events plus any ancestor events it
      received. Use for chain-of-custody verification, where downstream code
      needs visibility into the full lineage of upstream workflows.
    """

    NONE = int(pb.HISTORY_PROPAGATION_SCOPE_NONE)
    OWN_HISTORY = int(pb.HISTORY_PROPAGATION_SCOPE_OWN_HISTORY)
    LINEAGE = int(pb.HISTORY_PROPAGATION_SCOPE_LINEAGE)


class PropagationNotFoundError(Exception):
    """Raised when a query against propagated history finds no match."""


@dataclass(frozen=True)
class ActivityResult:
    """A reconstructed view of a single activity invocation from propagated history.

    ``input``/``output`` are the JSON-encoded string payloads or ``None`` when
    unset. ``error`` is ``None`` unless the activity failed.
    """

    name: str
    started: bool
    completed: bool
    failed: bool
    input: Optional[str]
    output: Optional[str]
    error: Optional[pb.TaskFailureDetails]


@dataclass(frozen=True)
class ChildWorkflowResult:
    """A reconstructed view of a single child workflow invocation."""

    name: str
    started: bool
    completed: bool
    failed: bool
    output: Optional[str]
    error: Optional[pb.TaskFailureDetails]


def _string_value_or_none(sv: Optional[pb.wrappers_pb2.StringValue]) -> Optional[str]:
    if sv is None or pbh.is_empty(sv):
        return None
    return sv.value


def _resolve_activity(
    events: list[pb.HistoryEvent], schedule_event: pb.HistoryEvent
) -> ActivityResult:
    """Build an ActivityResult by matching TaskCompleted/TaskFailed against the
    given TaskScheduled event's eventId. SDK retries reuse taskExecutionId, so
    we match on the scheduling event ID instead."""
    ts = schedule_event.taskScheduled
    schedule_id = schedule_event.eventId
    completed = False
    failed = False
    output: Optional[str] = None
    error: Optional[pb.TaskFailureDetails] = None
    for e in events:
        if e.HasField('taskCompleted') and e.taskCompleted.taskScheduledId == schedule_id:
            completed = True
            output = _string_value_or_none(e.taskCompleted.result)
        elif e.HasField('taskFailed') and e.taskFailed.taskScheduledId == schedule_id:
            failed = True
            error = e.taskFailed.failureDetails
    return ActivityResult(
        name=ts.name,
        started=True,
        completed=completed,
        failed=failed,
        input=_string_value_or_none(ts.input),
        output=output,
        error=error,
    )


def _resolve_child_workflow(
    events: list[pb.HistoryEvent], creation_event_id: int, name: str
) -> ChildWorkflowResult:
    completed = False
    failed = False
    output: Optional[str] = None
    error: Optional[pb.TaskFailureDetails] = None
    for e in events:
        if (
            e.HasField('childWorkflowInstanceCompleted')
            and e.childWorkflowInstanceCompleted.taskScheduledId == creation_event_id
        ):
            completed = True
            output = _string_value_or_none(e.childWorkflowInstanceCompleted.result)
        elif (
            e.HasField('childWorkflowInstanceFailed')
            and e.childWorkflowInstanceFailed.taskScheduledId == creation_event_id
        ):
            failed = True
            error = e.childWorkflowInstanceFailed.failureDetails
    return ChildWorkflowResult(
        name=name,
        started=True,
        completed=completed,
        failed=failed,
        output=output,
        error=error,
    )


@dataclass(frozen=True)
class WorkflowResult:
    """A scoped view of a single workflow's chunk in propagated history.

    Use :meth:`get_last_activity_by_name` / :meth:`get_last_child_workflow_by_name`
    to query specific items inside this chunk. Methods return the most-recent
    occurrence by execution order.
    """

    instance_id: str
    app_id: str
    name: str
    _events: list[pb.HistoryEvent] = field(repr=False)

    def get_activities_by_name(self, name: str) -> list[ActivityResult]:
        """Return every activity in this chunk whose scheduled name matches, in
        execution order. Empty list if none.

        See also: :meth:`get_last_activity_by_name` for the most recent match only.
        """
        return [
            _resolve_activity(self._events, e)
            for e in self._events
            if e.HasField('taskScheduled') and e.taskScheduled.name == name
        ]

    def get_last_activity_by_name(self, name: str) -> ActivityResult:
        """Return the most recent activity in this chunk whose name matches.

        Raises :class:`PropagationNotFoundError` if no activity scheduled with
        ``name`` is present.

        See also: :meth:`get_activities_by_name` to get every invocation in
        execution order (e.g. when an activity is retried or called in a loop).
        """
        all_results = self.get_activities_by_name(name)
        if not all_results:
            raise PropagationNotFoundError(
                f'no activity named {name!r} in propagated history for workflow {self.name!r}'
            )
        return all_results[-1]

    def get_child_workflows_by_name(self, name: str) -> list[ChildWorkflowResult]:
        """Return every child workflow in this chunk whose name matches, in
        execution order.

        See also: :meth:`get_last_child_workflow_by_name` for the most recent match.
        """
        return [
            _resolve_child_workflow(self._events, e.eventId, name)
            for e in self._events
            if e.HasField('childWorkflowInstanceCreated')
            and e.childWorkflowInstanceCreated.name == name
        ]

    def get_last_child_workflow_by_name(self, name: str) -> ChildWorkflowResult:
        """Return the most recent child workflow in this chunk whose name matches.

        Raises :class:`PropagationNotFoundError` if no match is found.

        See also: :meth:`get_child_workflows_by_name` to get every invocation
        in execution order when the same child workflow is started more than once.
        """
        all_results = self.get_child_workflows_by_name(name)
        if not all_results:
            raise PropagationNotFoundError(
                f'no child workflow named {name!r} in propagated history for workflow {self.name!r}'
            )
        return all_results[-1]


@dataclass(frozen=True)
class _HistoryChunk:
    app_id: str
    instance_id: str
    workflow_name: str
    start_event_index: int
    event_count: int


class PropagatedHistory:
    """History propagated from a parent workflow to a child workflow or activity.

    A propagated history is composed of one or more chunks, each owned by a
    distinct workflow instance. Chunks preserve execution order: index 0 is
    the oldest ancestor, the last chunk is the immediate parent. Use the
    ``get_*`` methods to slice the chain by app, instance, or workflow name.

    Attributes:
        events: All propagated history events, flattened in chunk order.
            Treat as read-only; mutating the list breaks the chunk index.
        scope: The propagation scope used to produce this history.
    """

    def __init__(
        self,
        events: list[pb.HistoryEvent],
        scope: PropagationScope,
        chunks: list[_HistoryChunk],
    ):
        self.events = events
        self.scope = scope
        self._chunks = chunks

    def get_app_ids(self) -> list[str]:
        """Ordered, deduplicated list of app IDs in the history chain."""
        seen: set[str] = set()
        result: list[str] = []
        for c in self._chunks:
            if c.app_id not in seen:
                seen.add(c.app_id)
                result.append(c.app_id)
        return result

    def _chunk_events(self, chunk: _HistoryChunk) -> list[pb.HistoryEvent]:
        return self.events[chunk.start_event_index : chunk.start_event_index + chunk.event_count]

    def get_events_by_app_id(self, app_id: str) -> list[pb.HistoryEvent]:
        """Events produced by the given app, in execution order."""
        return [
            event
            for chunk in self._chunks
            if chunk.app_id == app_id
            for event in self._chunk_events(chunk)
        ]

    def get_events_by_instance_id(self, instance_id: str) -> list[pb.HistoryEvent]:
        """Events produced by the given workflow instance, in execution order."""
        return [
            event
            for chunk in self._chunks
            if chunk.instance_id == instance_id
            for event in self._chunk_events(chunk)
        ]

    def get_events_by_workflow_name(self, workflow_name: str) -> list[pb.HistoryEvent]:
        """Events produced by workflows with the given name, in execution order."""
        return [
            event
            for chunk in self._chunks
            if chunk.workflow_name == workflow_name
            for event in self._chunk_events(chunk)
        ]

    def _make_workflow_result(self, chunk: _HistoryChunk) -> WorkflowResult:
        return WorkflowResult(
            instance_id=chunk.instance_id,
            app_id=chunk.app_id,
            name=chunk.workflow_name,
            _events=self._chunk_events(chunk),
        )

    def get_workflows(self) -> list[WorkflowResult]:
        """All workflow results in the chain, in execution order
        (ancestor first, immediate parent last)."""
        return [self._make_workflow_result(c) for c in self._chunks]

    def get_workflows_by_name(self, name: str) -> list[WorkflowResult]:
        """All workflows whose name matches, in execution order. Useful when
        the chain contains the same name more than once (recursion / ContinueAsNew).

        See also: :meth:`get_last_workflow_by_name` for a single-result helper that
        returns only the most recent match.
        """
        return [self._make_workflow_result(c) for c in self._chunks if c.workflow_name == name]

    def get_last_workflow_by_name(self, name: str) -> WorkflowResult:
        """Most recent workflow in the chain whose name matches.

        Raises :class:`PropagationNotFoundError` if no match is found.

        See also: :meth:`get_workflows_by_name` to get every matching workflow
        in execution order when the same name appears more than once.
        """
        all_results = self.get_workflows_by_name(name)
        if not all_results:
            raise PropagationNotFoundError(f'no workflow named {name!r} in propagated history')
        return all_results[-1]

    @classmethod
    def from_proto(
        cls, propagated_history: Optional[pb.PropagatedHistory]
    ) -> Optional[PropagatedHistory]:
        """Build a :class:`PropagatedHistory` from the wire-form proto.

        Each chunk's ``rawEvents`` are parsed once and the per-chunk events are
        concatenated into a single ordered list. Returns ``None`` when the
        proto itself is ``None``.

        Validation policy:

        * ``appId`` is the only required field per chunk. It anchors the
          chunk's signing identity in the chain of custody, so an empty
          ``appId`` is treated as structurally invalid and rejected.
        * ``instanceId`` and ``workflowName`` are best-effort metadata used
          only by the query helpers. Some sidecars may not populate
          ``workflowName`` at all, so they are accepted as empty rather than
          rejected here.
        * A ``rawEvents`` entry that fails to decode is fatal for the entire
          history: a chunk's ``HistoryEvent`` count and the indices used by
          downstream queries are derived from this loop, so silently dropping
          a bad event would leave the structure internally inconsistent (e.g.
          a TaskCompleted without its TaskScheduled). Fail at the trust
          boundary instead.

        Raises:
            ValueError: If the proto is structurally malformed (empty
                ``appId`` or an unparseable ``rawEvents`` entry).
        """
        if propagated_history is None:
            return None

        events: list[pb.HistoryEvent] = []
        chunks: list[_HistoryChunk] = []
        for i, c in enumerate(propagated_history.chunks):
            if not c.appId:
                raise ValueError(f'propagated history: chunk {i} has empty appId')
            start = len(events)
            for j, raw in enumerate(c.rawEvents):
                event = pb.HistoryEvent()
                try:
                    event.ParseFromString(raw)
                except Exception as ex:
                    raise ValueError(
                        f'propagated history: chunk {i} (app {c.appId!r}): '
                        f'failed to decode rawEvent {j}: {ex}'
                    ) from ex
                events.append(event)
            chunks.append(
                _HistoryChunk(
                    app_id=c.appId,
                    instance_id=c.instanceId,
                    workflow_name=c.workflowName,
                    start_event_index=start,
                    event_count=len(events) - start,
                )
            )
        return cls(
            events=events,
            scope=PropagationScope(propagated_history.scope),
            chunks=chunks,
        )
